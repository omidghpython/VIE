"""Frozen 15-question final evaluation of the controlled one-step experiment.

Plans are generated once by the original max4 generation function (max 2 structure
attempts), without review or semantic repair. Both arms reuse exactly these plans.
"""
from __future__ import annotations
from collections import Counter
import copy
from pathlib import Path
import time
import zipfile
from .common import ROOT, atomic_json, digest, file_digest, read_json, read_jsonl, question_digest, source_identity, verify_baseline, write_jsonl
from .dataset import CONDITIONS
from .prompts import SYSTEM
from .runner import validate_config, output_lock, run_experiment, summarize_run
from .reporting import export_report
from hotpotqa_operadic_rag.decomposition import generate_plan, DecompositionError
from hotpotqa_operadic_rag.contracts import validate_plan

GENERATION = dict(max_input_tokens=8500,max_output_tokens=3072,max_structure_attempts=2,
                  function='unchanged max4 generate_plan',semantic_review=False,semantic_repair=False)


def load_final15(check_private=False):
    manifest=read_json(ROOT/'data/final15_manifest.json')
    questions=read_jsonl(ROOT/'data/final15_questions.jsonl')
    registry=read_json(ROOT/'data/split_registry.json')
    exposure=read_json(ROOT/'provenance/known_exposure_registry.json')
    if len(questions)!=15 or len({q['question_id'] for q in questions})!=15:
        raise ValueError('Final evaluation requires exactly 15 unique questions')
    if manifest['question_count']!=15 or digest(questions)!=manifest['public_records_sha256']:
        raise ValueError('Final question manifest differs')
    if manifest['question_ids']!=[q['question_id'] for q in questions]:
        raise ValueError('Final ID order differs')
    if dict(Counter(q['question_type'] for q in questions))!={'bridge':8,'comparison':7}:
        raise ValueError('Frozen final type allocation differs')
    if digest(registry['heldout'])!=manifest['registry_sha256'] or digest(exposure)!=manifest['known_exposure_sha256']:
        raise ValueError('Final registration or exposure registry differs')
    excluded_ids=set(exposure['question_ids'])|{q['question_id'] for q in registry['development']}
    excluded_hashes=set(exposure['question_hashes'])|{q['question_sha256'] for q in registry['development']}
    registered={q['question_id']:q for q in registry['heldout']}
    hashes, case_ids=set(),set()
    for q in questions:
        if set(q)!={'question_id','question','question_type','split','states'} or q['split']!='heldout':
            raise ValueError('Invalid public final schema; gold fields are forbidden')
        qh=question_digest(q['question'])
        if q['question_id'] in excluded_ids or qh in excluded_hashes or qh in hashes:
            raise ValueError('Final question overlaps known development/exposure')
        hashes.add(qh)
        if registered[q['question_id']]['public_record_sha256']!=digest(q):
            raise ValueError('Registered final record changed')
        if len(q['states'])!=5:
            raise ValueError('Each final question requires the five frozen evidence states')
        for state in q['states']:
            if set(state)!={'case_id','evidence'} or state['case_id'] in case_ids:
                raise ValueError('Invalid/duplicate final evidence state')
            case_ids.add(state['case_id'])
    if len(case_ids)!=75:
        raise ValueError('Final state count must be 75, from 15 independent questions')
    if check_private:
        if digest(read_jsonl(ROOT/'private/final15_labels.jsonl'))!=manifest['labels_sha256']:
            raise ValueError('Private reference labels changed')
        if digest(read_json(ROOT/'private/final15_original_records.json'))!=manifest['originals_sha256']:
            raise ValueError('Original selected records changed')
    return questions,manifest


def freeze_identity(config):
    validate_config(config)
    if config['role']!='heldout':raise ValueError('Final configuration must declare heldout')
    questions,manifest=load_final15()
    baseline=verify_baseline()
    return dict(protocol='final15_one_step_structure_ablation_v1',decision_config=config,
                generation=GENERATION,source_sha256=source_identity(),prompt_sha256=digest(SYSTEM),
                baseline_zip_sha256=baseline['baseline_zip_sha256'],
                final_manifest_sha256=digest(manifest),public_questions_sha256=digest(questions),
                labels_file_sha256=file_digest(ROOT/'private/final15_labels.jsonl'),
                count=15,states=75)


def freeze_final15(config,output):
    identity=freeze_identity(config)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    marker=ROOT/'data/final15_usage.json'
    if marker.exists():
        prior=read_json(marker)
        if prior['freeze_identity_sha256']!=digest(identity) or prior['output_directory']!=str(output.resolve()):
            raise ValueError('These final questions were already opened for another run/configuration. Do not reuse them for tuning.')
    path=output/'FINAL15_LOCK.json'
    if path.exists():
        if read_json(path)['identity']!=identity:
            raise ValueError('Final evaluation is frozen; changed settings/source/data are refused')
    else:
        if list(output.iterdir()):raise ValueError('Use an empty final output directory')
        atomic_json(path,dict(identity=identity,identity_sha256=digest(identity),evaluation_started=False))
    return identity


class PendingUsage(RuntimeError):
    pass


class FrozenGenerationAdapter:
    plan_tokens=3072
    def __init__(self,backend,config,question,output):
        self.backend,self.config,self.question,self.output=backend,config,question,Path(output)
        self.attempt=0

    def generate(self,messages,max_new_tokens=None):
        self.attempt+=1
        if self.attempt>2 or max_new_tokens!=3072:
            raise ValueError('Original max4 generation allowance was exceeded')
        call_id=digest([self.question['question_id'],self.attempt])[:24]
        path=self.output/'generation_calls'/(call_id+'.json')
        signature=digest(messages)
        if path.exists():
            saved=read_json(path)
            if saved['messages_sha256']!=signature:raise ValueError('Resumed generation inputs changed')
            if saved['status'] in {'inflight','interrupted_usage_unknown'}:
                raise PendingUsage('Interrupted generation usage is unresolved; no automatic rerun')
            if saved['status']!='completed':raise RuntimeError('Previously failed generation; no automatic model retry')
            return saved['raw_output']
        row=dict(question_id=self.question['question_id'],attempt=self.attempt,messages=messages,
                 messages_sha256=signature,status='pending',raw_output=None,error=None,
                 usage=dict(llm_calls=0,prompt_tokens=0,completion_tokens=0,total_tokens=0,generation_seconds=0.0))
        start=time.perf_counter()
        try:
            length=self.backend.count_tokens(messages)
            row['input_tokens_measured']=length
            if length>8500:raise ValueError('Generation input exceeds original 8500-token cap; no truncation')
            self.backend.check_context(length,3072)
        except Exception as exc:
            row.update(status='input_rejected',error=str(exc),elapsed_seconds=time.perf_counter()-start)
            atomic_json(path,row)
            raise RuntimeError(str(exc)) from exc
        row['status']='inflight'
        row['usage'].update(llm_calls=1,prompt_tokens=length,completion_tokens=None,total_tokens=None,generation_seconds=None)
        atomic_json(path,row)
        try:
            response=self.backend.generate(messages,3072,self.config['seed'])
            row['raw_output']=response.text
            row['usage'].update(prompt_tokens=response.prompt_tokens,completion_tokens=response.completion_tokens,
                                total_tokens=response.prompt_tokens+response.completion_tokens,generation_seconds=response.generation_seconds)
            if response.prompt_tokens!=length:raise RuntimeError('Generation tokenization changed')
            if response.output_limit:
                row.update(status='output_limit',error='Generation reached output cap without EOS')
            else:row['status']='completed'
        except KeyboardInterrupt:
            row.update(status='interrupted_usage_unknown',error='Generation interrupted; output usage unknown')
            raise
        except Exception as exc:
            row.update(status='model_error',error=f'{type(exc).__name__}: {exc}')
        finally:
            row['elapsed_seconds']=time.perf_counter()-start
            atomic_json(path,row)
        if row['status']!='completed':raise RuntimeError(row['error'])
        return row['raw_output']


def make_final_cases(questions,plans):
    cases=[]
    for q in questions:
        result=plans[q['question_id']]
        plan=result.get('plan')
        for state in q['states']:
            cases.append(dict(schema_version=1,case_id=state['case_id'],source_question_id=q['question_id'],
                              split='heldout',question=q['question'],question_type=q['question_type'],
                              plan=plan,plan_sha256=digest(plan),structure_valid=result['status']=='valid',
                              evidence=state['evidence']))
    return cases


def generate_final_plans(questions,config,backend,output,progress=print):
    output=Path(output);plans={}
    for q in questions:
        path=output/'plans'/(q['question_id']+'.json')
        if path.exists():
            result=read_json(path)
            if result['question_sha256']!=question_digest(q['question']):raise ValueError('Frozen question changed')
            if digest(result.get('plan'))!=result['plan_sha256']:raise ValueError('Stored final plan was edited')
            if result['status']=='valid':validate_plan(result['plan'],max_nodes=4)
            plans[q['question_id']]=result
            continue
        adapter=FrozenGenerationAdapter(backend,config,q,output)
        result=dict(question_id=q['question_id'],question_sha256=question_digest(q['question']),
                    status='pending',plan=None,trace=[],error=None)
        try:
            plan,trace=generate_plan(adapter,q['question'])
            result.update(status='valid',plan=plan,trace=trace)
        except PendingUsage:
            raise
        except DecompositionError as exc:
            result.update(status='invalid',error=str(exc),trace=exc.details['decomposition_trace'])
        except Exception as exc:
            result.update(status='generation_error',error=f'{type(exc).__name__}: {exc}')
        result['plan_sha256']=digest(result['plan'])
        atomic_json(path,result);plans[q['question_id']]=result
        progress(f"Final plan {len(plans)}/15: {result['status']}")
    return plans


def run_final15(config,backend,output,progress=print):
    output=Path(output)
    identity=freeze_final15(config,output)
    questions,manifest=load_final15()
    with output_lock(output):
        runtime_path=output/'FINAL15_RUNTIME.json'
        runtime=dict(backend=backend.identity,freeze_identity_sha256=digest(identity))
        if runtime_path.exists() and read_json(runtime_path)!=runtime:
            raise ValueError('Final runtime identity changed; mixed-runtime evaluation refused')
        atomic_json(runtime_path,runtime)
        atomic_json(ROOT/'data/final15_usage.json',dict(freeze_identity_sha256=digest(identity),
                                                     output_directory=str(output.resolve()),
                                                     status='opened_for_model_run',question_count=15))
        atomic_json(output/'FINAL15_LOCK.json',dict(identity=identity,identity_sha256=digest(identity),evaluation_started=True))
        plans=generate_final_plans(questions,config,backend,output,progress)
        cases=make_final_cases(questions,plans)
        path=output/'prepared_final15_cases.jsonl'
        if path.exists() and read_jsonl(path)!=cases:raise ValueError('Final prepared plans/evidence changed')
        write_jsonl(path,cases)
        run_experiment(cases,config,backend,output/'decisions',progress=progress)
    return final_report(output)


def final_report(output):
    output=Path(output)
    if (output/'decisions/manifest.json').exists():
        export_report(output/'decisions')
        decision=summarize_run(output/'decisions')
    else:
        decision=dict(status='not_started',execution_complete=False,expected_trials=150,recorded_trials=0,
                      arms={arm:dict(llm_calls=0,total_tokens=0) for arm in ['structured','flat']})
    calls=[read_json(p) for p in sorted((output/'generation_calls').glob('*.json'))]
    plans=[read_json(p) for p in sorted((output/'plans').glob('*.json'))]
    unknown=any(c['usage']['total_tokens'] is None for c in calls)
    generation=dict(llm_calls=sum(c['usage']['llm_calls'] for c in calls),
                    known_total_tokens=sum(c['usage']['total_tokens'] or 0 for c in calls),
                    total_tokens=None if unknown else sum(c['usage']['total_tokens'] for c in calls),
                    unknown_usage_calls=sum(c['usage']['total_tokens'] is None for c in calls),
                    plan_statuses=dict(Counter(p['status'] for p in plans)))
    all_known=not unknown and all(a['total_tokens'] is not None for a in decision['arms'].values())
    summary=dict(question_count=15,state_count=75,completed_plan_records=len(plans),role='heldout',generation=generation,decision=decision,
                 total_model_calls=generation['llm_calls']+sum(a['llm_calls'] for a in decision['arms'].values()),
                 total_tokens=generation['total_tokens']+sum(a['total_tokens'] for a in decision['arms'].values()) if all_known else None,
                 execution_complete=len(plans)==15 and decision['execution_complete'],
                 cost_note='One shared plan per question; generation cost counted once in total, not once per evidence state.',
                 retrieval_calls=0,scope='Final evaluation of controlled one-step decisions; not end-to-end RAG.',
                 independent_evaluation_complete=False)
    evaluation=output/'decisions/evaluation.json'
    if evaluation.exists():summary['independent_evaluation_complete']=read_json(evaluation)['evaluation_complete']
    atomic_json(output/'final15_summary.json',summary)
    (output/'FINAL15_REPORT_FA.txt').write_text(
        'ارزیابی نهایی مرحلهٔ تصمیم‌گیری — ۱۵ سؤال مستقل، ۷۵ وضعیت شاهد\n'
        'این اجرا از۴۰سؤال توسعه جداست. query پیشنهادی اجرا نشده و نتیجهٔ RAG کامل نیست.\n'
        f"رکورد تولید درخت: {len(plans)} از۱۵؛ رکورد تصمیم: {decision['recorded_trials']} از۱۵۰\n"
        f"تکمیل اجرا: {summary['execution_complete']}؛ تکمیل داوری مستقل: {summary['independent_evaluation_complete']}\n"
        f"فراخوانی تولید درخت: {generation['llm_calls']}؛ کل فراخوانی: {summary['total_model_calls']}\n"
        f"کل توکن: {summary['total_tokens'] if all_known else 'نامعلوم؛ صفر نیست'}\n"
        'هر سؤال ناموفق در مخرج۱۵ باقی می‌ماند و جایگزین نمی‌شود.\n'
        'هزینهٔ هر حالت تصمیم در decisions/summary.json و هزینهٔ تولید مشترک در final15_summary.json است.\n',encoding='utf-8')
    return summary


def bundle_final15(output,destination):
    output,destination=Path(output),Path(destination)
    if (output/'.run.lock').exists():raise RuntimeError('Final evaluation is still running')
    final_report(output)
    if destination.exists():raise ValueError('Result bundle already exists; use a new filename')
    if output.resolve() in destination.resolve().parents:raise ValueError('Store result ZIP outside its input directory')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(output.rglob('*')):
            if p.is_file() and p.suffix in {'.json','.jsonl','.csv','.txt','.md'}:
                archive.write(p,arcname='final15_results/'+str(p.relative_to(output)))
    return dict(output=str(destination),question_count=15)
