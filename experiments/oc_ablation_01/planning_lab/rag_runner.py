"""Frozen, budget-matched three-arm RAG execution. Gold never enters runtime."""
import copy
from pathlib import Path
import time
from .common import ROOT, atomic_json, digest, file_digest, read_json, read_jsonl, source_identity, verify_baseline
from .dataset import validate_split
from .final15 import load_final15
from .runner import output_lock
from .rag_methods import METHODS
from .rag_retrieval import passages_from_states
from .rag_runtime import Session, TrackedRetriever, BudgetedQwen, BudgetExceeded, UnknownUsage
from .rag_support import cite_final_answer
from .console import notify
from hotpotqa_operadic_rag.contracts import validate_plan
from hotpotqa_operadic_rag.decomposition import generate_plan, DecompositionError

PROTOCOL = 'oc_ablation_01_dev40'


def validate_rag_config(config):
    expected = {'protocol','role','model','model_revision','allow_model_download','seed','retriever',
                'max_input_tokens','intermediate_tokens','answer_tokens','max_total_tokens','max_llm_calls',
                'max_retrieval_calls','top_k'}
    if set(config) != expected or config['protocol'] != PROTOCOL or config['role'] != 'development':
        raise ValueError('Invalid RAG protocol configuration')
    if config['model'] != 'Qwen/Qwen2.5-7B-Instruct' or config['model_revision'] != 'a09a35458c702b33eeacc393d103063234e8bc28':
        raise ValueError('Model identity must stay at the accepted baseline')
    if config['retriever'] not in {'hybrid','bm25'} or type(config['allow_model_download']) is not bool:
        raise ValueError('Invalid shared retriever or model options')
    for name in ['max_input_tokens','intermediate_tokens','answer_tokens','max_total_tokens','max_llm_calls']:
        if type(config[name]) is not int or config[name] < 1:
            raise ValueError('Invalid positive budget: '+name)
    if type(config['seed']) is not int or config['max_retrieval_calls'] != 2 or config['top_k'] != 3:
        raise ValueError('Use the baseline two retrieval rounds / three new passages per round')


def load_questions(role):
    verify_baseline()
    if role == 'development':
        cases = read_jsonl(ROOT/'data/development_cases.jsonl')
        manifest = read_json(ROOT/'data/development_manifest.json')
        if digest(cases) != manifest['cases_sha256']:
            raise ValueError('Development data changed')
        registry = read_json(ROOT/'data/split_registry.json')
        if digest(registry['development']) != manifest['questions_sha256']:
            raise ValueError('Development registry changed')
        validate_split(cases,role,registry)
        by_q = {}
        for c in cases:
            by_q.setdefault(c['source_question_id'],[]).append(c)
        result = []
        for row in registry['development']:
            states = by_q[row['question_id']]
            first = states[0]
            result.append(dict(question_id=row['question_id'],question=first['question'],
                question_type=first['question_type'],role=role,passages=passages_from_states(states),
                frozen_plan=first['plan'],structure_valid=first['structure_valid'],
                plan_debit={k:row['recorded_generation_cost'][k] for k in ['llm_calls','total_tokens']}))
        return result
    if role != 'heldout':
        raise ValueError('Unknown split')
    questions,_ = load_final15()
    return [dict(question_id=q['question_id'],question=q['question'],question_type=q['question_type'],
                 role=role,passages=passages_from_states(q['states'])) for q in questions]


def freeze_rag(config, questions, output):
    validate_rag_config(config)
    verify_baseline()
    if not questions or len({q['question_id'] for q in questions}) != len(questions):
        raise ValueError('Empty or duplicate question set')
    if any(q['role'] != config['role'] for q in questions):
        raise ValueError('Mixed dataset roles')
    allowed = {'question_id','question','question_type','role','passages','frozen_plan','structure_valid','plan_debit'}
    if any(set(q)-allowed for q in questions):
        raise ValueError('Extra runtime fields (including reference labels) are forbidden')
    if config['role']=='development':
        registered={q['question_id']:q for q in load_questions('development')}
        if any(registered.get(q['question_id'])!=q for q in questions):
            raise ValueError('Development question, frozen plan or corpus differs from registry')
    if config['role'] == 'heldout':
        if len(questions) != 15 or questions != load_questions('heldout'):
            raise ValueError('Final RAG requires all 15 exact frozen questions; no selection or replacement')
    identity = dict(config=config,questions_sha256=digest(questions),source_sha256=source_identity(),
                    entrypoint_sha256=file_digest(ROOT/'run_pair.py'),
                    baseline_sha256=verify_baseline()['baseline_zip_sha256'],methods=list(METHODS),
                    reference_labels_sha256=file_digest(ROOT/('private/final15_labels.jsonl' if config['role']=='heldout'
                                                              else 'private/development_labels.jsonl')))
    output = Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if config['role']=='heldout' and (ROOT/'data/final15_usage.json').exists():
        marker=read_json(ROOT/'data/final15_usage.json')
        if marker.get('freeze_identity_sha256')!=digest(identity) or marker.get('output_directory')!=str(output.resolve()):
            raise ValueError('Final15 was opened under another protocol/configuration/output; do not reuse it as unseen')
    path = output/'RAG_LOCK.json'
    if path.exists() and read_json(path)['identity'] != identity:
        raise ValueError('Source, dataset, settings or references changed; resume refused')
    atomic_json(path,dict(identity=identity,identity_sha256=digest(identity),question_count=len(questions),
                          expected_trials=len(questions)*len(METHODS),role=config['role']))
    return identity


def prepare_plan(question, config, backend, output, *, observer=None):
    path=Path(output)/'plans'/(question['question_id']+'.json')
    if path.exists():
        result=read_json(path)
        if result['question_sha256']!=digest(question['question']) or result['plan_sha256']!=digest(result.get('plan')):
            raise ValueError('Stored question/plan fingerprint changed')
        if result['status']=='valid':validate_plan(result['plan'],max_nodes=4)
        return result
    if 'frozen_plan' in question:
        result=dict(plan=question['frozen_plan'],status='valid' if question['structure_valid'] else 'invalid',
                    budget_debit=question['plan_debit'],actual_new_usage={'llm_calls':0,'total_tokens':0},
                    origin='historical_max4_frozen_plan',generation_trace=[],elapsed_seconds=None)
    else:
        started=time.perf_counter()
        had_prior_calls=any((Path(output)/'plan_calls'/question['question_id']/'model_calls').glob('*.json'))
        generation_config=dict(config,max_llm_calls=2)
        session=Session(backend,None,generation_config,Path(output)/'plan_calls'/question['question_id'],observer=observer)
        llm=BudgetedQwen(session)
        result=dict(plan=None,status='pending',origin='unchanged_max4_generate_plan',generation_trace=[])
        try:
            with session.phase('unchanged_max4_plan'):
                plan,trace=generate_plan(llm,question['question'])
            result.update(plan=plan,status='valid',generation_trace=trace)
        except DecompositionError as exc:
            result.update(status='invalid',error=str(exc),generation_trace=exc.details['decomposition_trace'])
        except Exception as exc:
            result.update(status='generation_error',error=f'{type(exc).__name__}: {exc}')
        usage=session.costs()
        result.update(actual_new_usage=usage,budget_debit={k:usage[k] for k in ['llm_calls','total_tokens']},
                      elapsed_seconds=None if had_prior_calls else time.perf_counter()-started)
    result.update(question_sha256=digest(question['question']),plan_sha256=digest(result['plan']))
    atomic_json(path,result)
    return result


def execute_trial(question, method, plan_record, config, backend, retriever, output, *, observer=None):
    output=Path(output)
    existing=sorted((output/'attempt_times').glob('*.json'))
    path=output/'attempt_times'/f'{len(existing):03}.json'
    atomic_json(path,dict(elapsed_seconds=None,status='running'))
    started=time.perf_counter()
    try:
        result=_execute_trial(question,method,plan_record,config,backend,retriever,output,observer=observer)
    finally:
        atomic_json(path,dict(elapsed_seconds=time.perf_counter()-started,status='returned_or_interrupted'))
    elapsed=[read_json(p)['elapsed_seconds'] for p in existing+[path]]
    result['execution_seconds']=None if any(t is None for t in elapsed) else sum(elapsed)
    result['shared_plan_seconds']=plan_record.get('elapsed_seconds') if method!='standard' else 0.
    result['charged_execution_seconds_with_plan']=(result['execution_seconds']+result['shared_plan_seconds']
        if result['execution_seconds'] is not None and result['shared_plan_seconds'] is not None else None)
    result['execution_time_scope']='Cumulative wall time across attempts; shared setup/generation reported separately.'
    return result


def _execute_trial(question, method, plan_record, config, backend, retriever, output, *, observer=None):
    debit=plan_record['budget_debit'] if method!='standard' else {'llm_calls':0,'total_tokens':0}
    # Invalid generation is retained in every denominator. Its unknown cost is
    # reported, never substituted with zero and never used to start another call.
    if method!='standard' and (plan_record['status']!='valid' or debit['total_tokens'] is None):
        return dict(question_id=question['question_id'],method=method,role=config['role'],status='invalid_plan',
                    answer='',citations=[],evidence_final=[],events=[],details={},
                    costs=dict(llm_calls=0,retrieval_calls=0,total_tokens=0,prompt_tokens=0,completion_tokens=0,
                        shared_plan_debit=debit,charged_llm_calls=debit['llm_calls'],charged_total_tokens=debit['total_tokens'],
                        generation_seconds=0.,retrieval_seconds=0.,unknown_usage=debit['total_tokens'] is None),
                    execution_seconds=0.,citation_status='no_answer',error=plan_record.get('error','Frozen tree invalid'))
    session=Session(backend,retriever,config,output,plan_debit=debit,observer=observer)
    llm=BudgetedQwen(session)
    started=time.perf_counter()
    result=dict(answer='',status='pending',citations=[],citation_status='no_answer',details={})
    try:
        result.update(METHODS[method](question['question'],copy.deepcopy(plan_record['plan']),TrackedRetriever(session),llm,session))
    except BudgetExceeded as exc:
        result.update(status='budget_exhausted',answer='',error=str(exc))
        session.event('controller_decision',action='budget_exhausted',reason=str(exc))
    except UnknownUsage as exc:
        result.update(status='usage_unknown',answer='',error=str(exc))
    except Exception as exc:
        result.update(status='execution_error',answer='',error=f'{type(exc).__name__}: {exc}')
    if result['answer']:
        try:
            with session.phase('common_final_citations'):
                result['citations']=cite_final_answer(llm,question['question'],result['answer'],session.evidence)
            result['citation_status']='attributed' if result['citations'] else 'unsupported_by_attributor'
        except Exception as exc:
            # A common reporting step must not retroactively alter the baseline answer.
            result['citation_status']='unavailable'
            result['citation_error']=f'{type(exc).__name__}: {exc}'
    result.update(question_id=question['question_id'],method=method,role=config['role'],
                  evidence_final=session.evidence,events=session.events,costs=session.costs(),
                  execution_seconds=time.perf_counter()-started,plan_sha256=plan_record['plan_sha256'],
                  semantic_support_guaranteed=False)
    return result


def prepare_retriever(question, retriever_factory, output):
    """Journal a question-local setup failure; do not retry a saved failure.

    File integrity/write failures and explicit process interruption still stop
    the run. They must not be disguised as successfully persisted trial results.
    """
    path = Path(output)/'retriever_setup'/(question['question_id']+'.json')
    setup = read_json(path) if path.exists() else dict(attempt_seconds=[], shared_across_methods=True)
    if setup.get('status') == 'failed':
        return None, setup
    setup.update(status='running')
    setup['attempt_seconds'].append(None)
    atomic_json(path, setup)
    started = time.perf_counter()
    retriever = None
    try:
        retriever = retriever_factory(question['passages'])
    except Exception as exc:
        setup.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                     error_type=type(exc).__name__)
    else:
        setup['status'] = 'completed'
    finally:
        setup['attempt_seconds'][-1] = time.perf_counter()-started
        if setup['status'] == 'running':
            setup['status'] = 'interrupted'
        atomic_json(path, setup)
    return retriever, setup


def setup_failure_trial(question, method, plan_record, config, setup):
    """No method/model/search ran; shared setup cost is reported separately."""
    debit = plan_record['budget_debit'] if method != 'standard' else {'llm_calls':0, 'total_tokens':0}
    invalid = method != 'standard' and (plan_record['status'] != 'valid' or debit['total_tokens'] is None)
    plan_seconds = plan_record.get('elapsed_seconds') if method != 'standard' else 0.
    return dict(question_id=question['question_id'], method=method, role=config['role'],
        answer='', status='invalid_plan' if invalid else 'retriever_setup_error',
        error=plan_record.get('error','Frozen tree invalid') if invalid else setup['error'],
        failure_stage='plan_validation' if invalid else 'retriever_setup',
        citations=[], citation_status='no_answer', evidence_final=[],
        details=dict(shared_retriever_setup=copy.deepcopy(setup), plan_status=plan_record['status']),
        events=[dict(kind='question_setup_failed', stage='retriever_setup', error=setup['error'])],
        costs=dict(llm_calls=0, retrieval_calls=0, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, known_tokens=0, unknown_usage=debit['total_tokens'] is None,
            shared_plan_debit=debit, charged_llm_calls=debit['llm_calls'],
            charged_total_tokens=debit['total_tokens'], generation_seconds=0., retrieval_seconds=0.),
        execution_seconds=0., shared_plan_seconds=plan_seconds,
        charged_execution_seconds_with_plan=plan_seconds,
        execution_time_scope='Method not started; failed shared retriever setup is accounted once in retriever_setup.',
        plan_sha256=plan_record['plan_sha256'], semantic_support_guaranteed=False)


def run_rag(questions,config,backend,retriever_factory,output,*,max_new_questions=None,progress=print,observer=None):
    if max_new_questions is not None and (type(max_new_questions) is not int or max_new_questions<1):
        raise ValueError('Session cap must allow at least one complete three-method question')
    output=Path(output)
    identity=freeze_rag(config,questions,output)
    runtime=dict(backend=backend.identity,retriever=retriever_factory.identity)
    if (output/'runtime.json').exists() and read_json(output/'runtime.json')!=runtime:
        raise ValueError('Model or retriever runtime identity changed')
    with output_lock(output):
        atomic_json(output/'runtime.json',runtime)
        atomic_json(output/'runtime_questions.json',questions)
        if config['role']=='heldout':
            atomic_json(ROOT/'data/final15_usage.json',dict(protocol=PROTOCOL,freeze_identity_sha256=digest(identity),
                output_directory=str(output.resolve()),status='opened_for_model_run',question_count=15))
        done=0
        ordered=sorted(questions,key=lambda q:digest([config['seed'],q['question_id']]))
        for index,question in enumerate(ordered):
            qid=question['question_id']
            order=list(METHODS)
            order=order[index%len(METHODS):]+order[:index%len(METHODS)]
            pending=[m for m in order if not (output/'trials'/f'{qid}--{m}.json').exists()]
            if not pending:
                notify(observer,'question_skipped',index=index+1,total=len(ordered),qid=qid)
                continue
            if max_new_questions is not None and done>=max_new_questions:break
            notify(observer,'question_started',index=index+1,total=len(ordered),qid=qid,
                   question_type=question['question_type'],question=question['question'],pending=pending)
            plan=prepare_plan(question,config,backend,output,observer=observer)
            notify(observer,'plan_ready',plan=plan['plan'],status=plan['status'],origin=plan['origin'],debit=plan['budget_debit'])
            notify(observer,'setup',message='Preparing the shared question-local retrieval index')
            retriever,setup=prepare_retriever(question,retriever_factory,output)
            notify(observer,'retriever_ready',setup=setup)
            for method in pending:
                notify(observer,'method_started',method=method)
                if setup['status']=='failed':
                    result=setup_failure_trial(question,method,plan,config,setup)
                else:
                    result=execute_trial(question,method,plan,config,backend,retriever,output/'calls'/qid/method,observer=observer)
                atomic_json(output/'trials'/f'{qid}--{method}.json',result)
                notify(observer,'method_completed',method=method,result=result)
                progress(f'{done+1}: {method}: {result["status"]}')
            done+=1
    summary=execution_summary(output)
    notify(observer,'run_completed',summary=summary)
    return summary


def execution_summary(output):
    output=Path(output)
    lock=read_json(output/'RAG_LOCK.json')
    trials=[read_json(p) for p in sorted((output/'trials').glob('*.json'))]
    plans=[read_json(p) for p in sorted((output/'plans').glob('*.json'))]
    shared=[p['actual_new_usage'] for p in plans]
    setup_times=[seconds for p in (output/'retriever_setup').glob('*.json')
                 for seconds in read_json(p)['attempt_seconds']]
    known=all(t['costs']['total_tokens'] is not None for t in trials) and all(p['total_tokens'] is not None for p in shared)
    summary=dict(protocol=PROTOCOL,role=lock['role'],question_count=lock['question_count'],
        expected_trials=lock['expected_trials'],recorded_trials=len(trials),execution_complete=len(trials)==lock['expected_trials'],
        actual_llm_calls=sum(t['costs']['llm_calls'] for t in trials)+sum(p['llm_calls'] for p in shared),
        actual_retrieval_calls=sum(t['costs']['retrieval_calls'] for t in trials),
        actual_total_tokens=sum(t['costs']['total_tokens'] for t in trials)+sum(p['total_tokens'] for p in shared) if known else None,
        shared_plan_calls=sum(p['llm_calls'] for p in shared),
        shared_retriever_setup_seconds=sum(setup_times) if all(t is not None for t in setup_times) else None,
        cost_scope='Physical calls count shared final-plan generation once; per-method charged cost includes it in each tree arm.',
        independent_semantic_evaluation_complete=False,methods=list(METHODS))
    atomic_json(output/'execution_summary.json',summary)
    return summary
