"""Real CPU retrieval + synthetic language outputs; never runs final15 inference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from planning_lab.backend import Response
from planning_lab.common import ROOT, atomic_json, canonical, digest, read_json, read_jsonl, write_jsonl
from planning_lab.rag_runtime import Session, BudgetedQwen, BudgetExceeded
from planning_lab.rag_retrieval import BM25Retriever, RetrieverFactory
from planning_lab.rag_methods import METHODS
from planning_lab.rag_support import check_support, stop_gate
from planning_lab import rag_runner as runner
from planning_lab import rag_evaluation as evaluation

CONFIG=dict(read_json(ROOT/'configs/rag_development.json'),retriever='bm25')
PLAN={'nodes':[
    {'id':'q1','question':'Who directed Example Film?','dependencies':{},'answer_type':'person'},
    {'id':'q2','question':'Where was {{q1}} born?','dependencies':{'q1':'person'},'answer_type':'place'}], 'final':'q2'}


def fixture(qid='synthetic-one'):
    texts=['Example Film was directed by Dana.',
           'Example Film director film directed Example Film review.',
           'Example Film director film directed Example Film production.',
           "Dana's birthplace is Bruma."]+['Unrelated document number '+str(i) for i in range(6)]
    passages=[dict(index=i,title='Document '+str(i),sentences=[text],sentence_ids=[0],text=text)
              for i,text in enumerate(texts)]
    return dict(question_id=qid,question='Where was the director of Example Film born?',question_type='bridge',
                role='development',passages=passages,frozen_plan=copy.deepcopy(PLAN),structure_valid=True,
                plan_debit={'llm_calls':1,'total_tokens':100})


def plan_record(q):
    return dict(plan=q['frozen_plan'],plan_sha256=digest(q['frozen_plan']),status='valid' if q['structure_valid'] else 'invalid',
                budget_debit=q['plan_debit'])


class ScriptBackend:
    identity={'backend':'synthetic_rag_software_test','live_inference':False}
    load_seconds=0.
    def __init__(self,mode='normal'):
        self.mode,self.messages=mode,[]
    def count_tokens(self,messages):return 100
    def check_context(self,prompt,output):pass
    def generate(self,messages,maximum,seed):
        self.messages.append(messages)
        if self.mode=='model_error':raise RuntimeError('Synthetic interrupted generate')
        user=messages[-1]['content']
        if 'Decompose Question into a small typed rooted TREE' in messages[0]['content']:
            result=copy.deepcopy(PLAN)
        elif user.startswith('RAG_SUPPORT_CHECK_V1'):
            data=json.loads(user.rsplit('\n',1)[1])
            supported=self.mode not in {'reject_support','unsupported_goal'} or (self.mode=='unsupported_goal' and data['scope']!='original_goal')
            support=[dict(ref=ref,quote=data['evidence'][ref]['sentence']) for ref in data['candidate_refs']]
            if self.mode=='fabricate_quote':support[0]['quote']='THIS SENTENCE IS NOT IN THE EVIDENCE'
            result=dict(supported=supported,entity='Dana',property='birthplace' if data['candidate']=='Bruma' else 'director',
                        value=data['candidate'],support=support,conflict=False,missing_query='' if supported else 'Dana birthplace',
                        reason='Synthetic verdict for software test')
        elif user.startswith('RAG_FINAL_CITATIONS_V1'):
            data=json.loads(user.rsplit('\n',1)[1])
            result={'refs':[ref for ref,e in data['evidence'].items() if 'directed by Dana' in e['sentence'] or 'birthplace is Bruma' in e['sentence']]}
        elif user.startswith('Decide whether the evidence contains all facts'):
            result={'is_sufficient':'birthplace is Bruma' in user,'follow_up_query':'Dana birthplace'}
        elif user.startswith('Audit cached Bindings'):
            result={'invalid':[]}
        elif user.startswith('Answer Node using only Evidence'):
            node=user.split('\nNode:\n',1)[1].split('\nAnswer type:',1)[0]
            if node.startswith('Who directed'):
                result={'answer':'Dana','refs':['0:0'],'need':''}
            elif 'birthplace is Bruma' in user:
                result={'answer':'Bruma','refs':['3:0'],'need':''}
            else:result={'answer':'','refs':[],'need':'Dana birthplace'}
        elif messages[0]['content'].startswith('Use only the supplied evidence. Return a factual answer'):
            return Response('Bruma' if 'birthplace is Bruma' in user else '',100,2,.001)
        else:raise AssertionError('Unexpected synthetic backend prompt: '+user[:100])
        return Response(canonical(result),100,20,.001)


class RagIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.output=Path(self.temp.name)
        self.q=fixture()
    def tearDown(self):self.temp.cleanup()
    def trial(self,method='operadic',backend=None,config=None,subdir='trial',retriever=None):
        return runner.execute_trial(self.q,method,plan_record(self.q),config or CONFIG,backend or ScriptBackend(),
            retriever or BM25Retriever(self.q['passages']),self.output/subdir)

    def test_all_three_execute_real_bm25_retrieval_with_new_evidence(self):
        for method in METHODS:
            result=self.trial(method,subdir=method)
            self.assertEqual(result['status'],'answered',result)
            self.assertEqual(result['answer'],'Bruma')
            self.assertEqual(result['costs']['retrieval_calls'],2)
            self.assertEqual(len(result['evidence_final']),6)
            searches=sorted((self.output/method/'retrieval_calls').glob('*.json'))
            first,second=[read_json(p) for p in searches]
            self.assertNotEqual(first['request']['query'],second['request']['query'])
            self.assertEqual(set(second['request']['exclude_indices']),{p['index'] for p in first['hits'][:3]})
            self.assertFalse({p['index'] for p in first['hits'][:3]} & {p['index'] for p in second['hits'][:3]})
            self.assertTrue(result['citations'])

    def test_actual_dependency_value_is_consumed_in_child_call(self):
        result=self.trial()
        inputs=[e for e in result['events'] if e['kind']=='node_inputs' and e['node_id']=='q2']
        self.assertTrue(inputs)
        self.assertTrue(all(e['consumed_dependencies']=={'q1':'Dana'} for e in inputs))
        self.assertTrue(all(e['resolved_question']=='Where was Dana born?' for e in inputs))
        self.assertTrue(all(e['input_bindings']['q1']['refs']==['0:0'] for e in inputs))

    def test_original_hybrid_retriever_is_executed_with_test_encoder(self):
        import numpy as np
        from hotpotqa_operadic_rag.retriever import HybridRetriever
        class ConstantEncoder:
            def encode(self,texts,**kwargs):return np.ones((len(texts),3),dtype=np.float32)/np.sqrt(3)
        retriever=HybridRetriever(self.q['passages'],encoder=ConstantEncoder())
        result=self.trial(retriever=retriever)
        self.assertEqual(result['status'],'answered')
        self.assertEqual(result['costs']['retrieval_calls'],2)
        self.assertTrue(all('hybrid_score' in p for p in result['evidence_final']))

    def test_failed_retrieval_is_counted_and_not_repeated(self):
        retriever=BM25Retriever(self.q['passages'])
        with patch.object(retriever,'search',side_effect=RuntimeError('Synthetic search failure')) as spy:
            first=self.trial(retriever=retriever)
            second=self.trial(retriever=retriever)
        self.assertEqual(spy.call_count,1)
        self.assertEqual(first['costs']['retrieval_calls'],1)
        self.assertEqual(second['costs']['retrieval_calls'],1)
        self.assertEqual(second['status'],'usage_unknown')

    def test_missing_prerequisite_blocks_child_and_successful_stop(self):
        result=self.trial(backend=ScriptBackend('reject_support'))
        self.assertEqual(result['status'],'budget_exhausted')
        self.assertEqual(result['answer'],'')
        self.assertTrue(any(e['kind']=='node_blocked' and e['node_id']=='q2' for e in result['events']))
        self.assertFalse(any(e['kind']=='node_inputs' and e['node_id']=='q2' for e in result['events']))
        self.assertFalse(any(e['kind']=='controller_decision' and e['action']=='stop' for e in result['events']))

    def test_goal_verification_blocks_supported_tree_with_wrong_goal(self):
        result=self.trial(backend=ScriptBackend('unsupported_goal'))
        self.assertEqual(result['status'],'budget_exhausted')
        self.assertFalse(result['answer'])
        self.assertTrue(any(e['kind']=='stop_gate' and not e['allowed'] for e in result['events']))

    def test_fabricated_evidence_quote_cannot_support_a_node(self):
        result=self.trial(backend=ScriptBackend('fabricate_quote'))
        self.assertEqual(result['status'],'budget_exhausted')
        checks=[e['certificate'] for e in result['events'] if e['kind']=='node_assessed']
        self.assertTrue(checks)
        self.assertTrue(all(not c['supported'] and not c['valid_format'] for c in checks))

    def test_evidence_change_invalidates_previous_bindings(self):
        result=self.trial()
        self.assertTrue(any(e['kind']=='cache_invalidated' and 'q1' in e['node_ids'] for e in result['events']))
        checks=[e for e in result['events'] if e['kind']=='node_inputs' and e['node_id']=='q1']
        self.assertEqual(len(checks),2)

    def test_all_methods_enforce_shared_call_budget_including_plan(self):
        for method in METHODS:
            result=self.trial(method,config=dict(CONFIG,max_llm_calls=1),subdir=method)
            self.assertLessEqual(result['costs']['charged_llm_calls'],1)
            if method!='standard':self.assertEqual(result['status'],'budget_exhausted')

    def test_token_budget_reserves_output_before_model_dispatch(self):
        backend=ScriptBackend()
        result=self.trial(backend=backend,config=dict(CONFIG,max_total_tokens=300))
        self.assertEqual(result['status'],'budget_exhausted')
        self.assertEqual(len(backend.messages),0)
        self.assertEqual(result['costs']['charged_total_tokens'],100)

    def test_baseline_plans_and_original_module_namespace_do_not_change(self):
        from hotpotqa_operadic_rag.methods import operadic as original
        before=original.decompose_question
        snapshot=digest(self.q['frozen_plan'])
        backend=ScriptBackend()
        self.trial('max4',backend=backend)
        self.assertIs(original.decompose_question,before)
        self.assertEqual(digest(self.q['frozen_plan']),snapshot)
        self.assertFalse(any('Decompose Question' in m[0]['content'] for m in backend.messages))

    def test_unknown_model_usage_not_retried_or_reported_zero(self):
        backend=ScriptBackend('model_error')
        first=self.trial(backend=backend)
        second=self.trial(backend=backend)
        self.assertEqual(len(backend.messages),1)
        self.assertIsNone(first['costs']['total_tokens'])
        self.assertIsNone(second['costs']['total_tokens'])
        self.assertEqual(second['status'],'usage_unknown')

    def test_truncated_model_output_is_charged_and_not_retried(self):
        backend=ScriptBackend()
        original=backend.generate
        def truncated(*args):
            response=original(*args)
            response.output_limit=True
            return response
        backend.generate=truncated
        first=self.trial(backend=backend)
        second=self.trial(backend=backend)
        self.assertEqual(len(backend.messages),1)
        self.assertEqual(first['costs']['total_tokens'],120)
        self.assertEqual(second['costs']['total_tokens'],120)
        self.assertEqual(first['status'],'execution_error')

    def test_replay_of_completed_calls_performs_no_new_model_or_search(self):
        backend=ScriptBackend()
        self.trial(backend=backend)
        count=len(backend.messages)
        retriever=BM25Retriever(self.q['passages'])
        with patch.object(retriever,'search',side_effect=AssertionError('Repeated retrieval')):
            result=self.trial(backend=backend,retriever=retriever)
        self.assertEqual(result['status'],'answered')
        self.assertEqual(len(backend.messages),count)

    def test_unfinished_prior_attempt_time_remains_unknown(self):
        atomic_json(self.output/'trial/attempt_times/000.json',{'elapsed_seconds':None,'status':'running'})
        result=self.trial()
        self.assertIsNone(result['execution_seconds'])

    def test_active_stop_gate_rejects_stale_dependency_value(self):
        states=[dict(id=n['id'],status='supported') for n in PLAN['nodes']]
        bindings={'q1':{'value':'Dana','consumed_dependencies':{}},
                  'q2':{'value':'Bruma','consumed_dependencies':{'q1':'Another Person'}}}
        gate=stop_gate(PLAN,bindings,states,{'supported':True,'valid_format':True,'conflict':False})
        self.assertFalse(gate['allowed'])
        self.assertEqual(gate['stale_or_missing_input_bindings'],['q2'])

    def test_invalid_plan_retained_and_standard_still_runs(self):
        self.q['structure_valid']=False
        for method in ['max4','operadic']:
            result=self.trial(method,subdir=method)
            self.assertEqual(result['status'],'invalid_plan')
            self.assertEqual(result['costs']['llm_calls'],0)
        self.assertEqual(self.trial('standard',subdir='standard')['status'],'answered')


class RagExperimentAndEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.output=Path(self.temp.name)/'results'
        self.questions=[fixture('synthetic-one'),fixture('synthetic-two')]
        self.questions[1]['structure_valid']=False
        self.backend=ScriptBackend()
        self.factory=RetrieverFactory(CONFIG)
        self.reference={q['question_id']:{'answer':'Bruma','supporting_facts':[['Document 0',0],['Document 3',0]]} for q in self.questions}
    def tearDown(self):self.temp.cleanup()
    def run_all(self,max_new=None):
        with patch.object(runner,'load_questions',return_value=self.questions):
            return runner.run_rag(self.questions,CONFIG,self.backend,self.factory,self.output,
                                  max_new_questions=max_new,progress=lambda _:None)

    def test_shared_runner_keeps_every_method_and_invalid_question(self):
        result=self.run_all()
        self.assertEqual(result['recorded_trials'],6)
        self.assertTrue(result['execution_complete'])
        self.assertGreater(result['actual_retrieval_calls'],0)
        self.assertEqual(result['shared_plan_calls'],0)

    def test_successful_resume_has_no_repeated_calls(self):
        self.run_all()
        count=len(self.backend.messages)
        self.run_all()
        self.assertEqual(len(self.backend.messages),count)

    def test_pause_only_between_complete_three_method_questions(self):
        summary=self.run_all(max_new=1)
        self.assertEqual(summary['recorded_trials'],3)
        self.assertFalse(summary['execution_complete'])
        final=self.run_all()
        self.assertEqual(final['recorded_trials'],6)

    def test_answer_accuracy_denominator_includes_failed_tree(self):
        self.run_all()
        with patch.object(evaluation,'references',return_value=self.reference):
            report=evaluation.report_rag(self.output)
        self.assertEqual(report['metrics']['standard']['answer_accuracy'],1.)
        self.assertEqual(report['metrics']['operadic']['answer_accuracy'],.5)
        self.assertEqual(report['metrics']['max4']['answer_accuracy'],.5)
        self.assertEqual(report['metrics']['operadic']['supporting_fact_coverage'],.5)
        self.assertIsNone(report['metrics']['operadic']['premature_stopping'])
        self.assertIsNone(report['metrics']['operadic']['citation_faithfulness'])

    def test_partial_execution_does_not_claim_final_answer_accuracy(self):
        self.run_all(max_new=1)
        with patch.object(evaluation,'references',return_value=self.reference):report=evaluation.report_rag(self.output)
        self.assertTrue(all(m['answer_accuracy'] is None for m in report['metrics'].values()))

    def test_config_change_refuses_resume(self):
        self.run_all()
        with patch.object(runner,'load_questions',return_value=self.questions):
            with self.assertRaises(ValueError):runner.freeze_rag(dict(CONFIG,max_llm_calls=23),self.questions,self.output)

    def test_runtime_cannot_receive_reference_answer(self):
        bad=copy.deepcopy(self.questions)
        bad[0]['answer']='GOLD_SENTINEL'
        with self.assertRaises(ValueError):runner.freeze_rag(CONFIG,bad,self.output)

    def test_manual_semantics_and_per_node_review_are_not_auto_filled(self):
        self.run_all()
        destination=self.output/'review'
        with patch.object(evaluation,'references',return_value=self.reference):evaluation.export_rag_review(self.output,destination)
        packets=read_jsonl(destination/'review_packets.jsonl')
        self.assertTrue(all(p['review']['state_sufficient'] is None for p in packets))
        self.assertTrue(any(p['review']['subquestions'] for p in packets))
        result=evaluation.score_rag_review(self.output,destination/'review_packets.jsonl',destination/'private_mapping.json')
        self.assertFalse(result['complete'])
        self.assertTrue(all(m['citation_faithfulness'] is None for m in result['metrics'].values()))

    def test_review_tampering_rejected(self):
        self.run_all()
        destination=self.output/'review'
        with patch.object(evaluation,'references',return_value=self.reference):evaluation.export_rag_review(self.output,destination)
        packets=read_jsonl(destination/'review_packets.jsonl')
        packets[0]['answer']='tampered'
        write_jsonl(destination/'review_packets.jsonl',packets)
        with self.assertRaises(ValueError):evaluation.score_rag_review(self.output,destination/'review_packets.jsonl',destination/'private_mapping.json')

    def test_independent_semantic_metrics_only_after_completed_annotations(self):
        self.run_all()
        destination=self.output/'review'
        with patch.object(evaluation,'references',return_value=self.reference):evaluation.export_rag_review(self.output,destination)
        packets=read_jsonl(destination/'review_packets.jsonl')
        for packet in packets:
            has_answer=bool(packet['answer'])
            packet['review'].update(final=True,reviewer_id='SYNTHETIC_TEST_REVIEWER',state_sufficient=has_answer,
                binding_correct=has_answer,cited_claims=int(has_answer),entailed_cited_claims=int(has_answer),
                required_claims=1,entailed_required_claims=int(has_answer))
            for row in packet['review']['subquestions']:
                row.update(support_assessment_correct=True,binding_correct=True)
        write_jsonl(destination/'review_packets.jsonl',packets)
        scored=evaluation.score_rag_review(self.output,destination/'review_packets.jsonl',destination/'private_mapping.json')
        self.assertTrue(scored['complete'])
        self.assertEqual(scored['metrics']['operadic']['premature_stopping'],0.)
        self.assertEqual(scored['metrics']['operadic']['citation_faithfulness'],1.)
        with patch.object(evaluation,'references',return_value=self.reference):report=evaluation.report_rag(self.output)
        self.assertTrue(report['execution']['independent_semantic_evaluation_complete'])
        self.assertEqual(report['paired_answer_comparisons'][1]['em_difference'],-.5)


class RagFinal15BoundaryTests(unittest.TestCase):
    def test_final_generation_failure_keeps_two_attempt_cost_and_no_replacement(self):
        class InvalidPlanBackend(ScriptBackend):
            def generate(self,messages,maximum,seed):
                self.messages.append(messages)
                return Response('{}',100,20,.001)
        q=fixture('synthetic-failed-plan')
        for key in ['frozen_plan','structure_valid','plan_debit']:q.pop(key)
        q['role']='heldout'
        with tempfile.TemporaryDirectory() as td:
            backend=InvalidPlanBackend()
            config=dict(CONFIG,role='heldout')
            plan=runner.prepare_plan(q,config,backend,Path(td))
            self.assertEqual(plan['status'],'invalid')
            self.assertEqual(plan['actual_new_usage']['llm_calls'],2)
            self.assertEqual(plan['budget_debit']['total_tokens'],240)
            for method in ['max4','operadic']:
                trial=runner.execute_trial(q,method,plan,config,backend,BM25Retriever(q['passages']),Path(td)/method)
                self.assertEqual(trial['status'],'invalid_plan')
            self.assertEqual(len(backend.messages),2)

    def test_final15_corpus_exists_without_using_private_answers(self):
        final=runner.load_questions('heldout')
        self.assertEqual(len(final),15)
        self.assertTrue(all(len(q['passages'])==10 for q in final))
        self.assertTrue(all('answer' not in q and 'supporting_facts' not in q for q in final))
        self.assertFalse((ROOT/'data/final15_usage.json').exists())

    def test_final_subset_is_refused_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                runner.freeze_rag(dict(CONFIG,role='heldout'),runner.load_questions('heldout')[:14],Path(td)/'out')

    def test_synthetic_final_lifecycle_and_cross_protocol_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'run_rag.py').write_text('# synthetic fixture')
            atomic_json(root/'private/final15_labels.jsonl',{})
            qs=[]
            for i in range(15):
                q=fixture('synthetic-heldout-'+str(i))
                for key in ['frozen_plan','structure_valid','plan_debit']:q.pop(key)
                q['role']='heldout'
                qs.append(q)
            config=dict(CONFIG,role='heldout')
            backend=ScriptBackend()
            factory=RetrieverFactory(config)
            with patch.object(runner,'ROOT',root),patch.object(runner,'load_questions',return_value=qs):
                out=root/'results'
                summary=runner.run_rag(qs,config,backend,factory,out,max_new_questions=1,progress=lambda _:None)
                self.assertEqual(summary['question_count'],15)
                self.assertEqual(summary['recorded_trials'],3)
                self.assertEqual(summary['shared_plan_calls'],1)
                self.assertTrue((root/'data/final15_usage.json').exists())
                with self.assertRaises(ValueError):runner.freeze_rag(config,qs,root/'another_run')
                with self.assertRaises(ValueError):runner.freeze_rag(dict(config,max_llm_calls=23),qs,out)
                complete=runner.run_rag(qs,config,backend,factory,out,progress=lambda _:None)
                self.assertTrue(complete['execution_complete'])
                self.assertEqual(complete['recorded_trials'],45)
                self.assertEqual(complete['shared_plan_calls'],15)
                trials=[read_json(p) for p in (out/'trials').glob('*.json')]
                self.assertEqual(complete['actual_llm_calls'],sum(t['costs']['llm_calls'] for t in trials)+15)
                self.assertTrue(all(t['costs']['shared_plan_debit']['llm_calls']==(0 if t['method']=='standard' else 1) for t in trials))


if __name__=='__main__':unittest.main()
