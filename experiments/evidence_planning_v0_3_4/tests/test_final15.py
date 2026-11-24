"""Final-run behavior tested on SYNTHETIC questions only; real final15 gets identity/schema checks only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from planning_lab.backend import Response
from planning_lab.common import ROOT, atomic_json, canonical, digest, question_digest, read_json, read_jsonl
from planning_lab.dataset import validate_split
from planning_lab.final15 import load_final15, freeze_final15, run_final15, FrozenGenerationAdapter, PendingUsage, bundle_final15
from planning_lab.cli import main

CONFIG=read_json(ROOT/'configs/final15.json')


def synthetic_questions():
    return [dict(question_id=f'synthetic-final-{i}',question=f'Who is SYNTHETIC PERSON {i}?',
                 question_type='bridge' if i<8 else 'comparison',split='heldout',
                 states=[dict(case_id=digest(['synthetic',i,j])[:24],evidence=[])
                         for j in range(5)]) for i in range(15)]


class SyntheticBackend:
    identity={'backend':'synthetic_test','test_only':True}
    load_seconds=0.0
    def __init__(self,invalid_first=False,interrupt=False):
        self.calls=0;self.plan_calls=0;self.decision_calls=0
        self.invalid_first=invalid_first;self.interrupt=interrupt
    def count_tokens(self,messages):return 100
    def check_context(self,prompt,output):pass
    def generate(self,messages,maximum,seed):
        self.calls+=1
        if self.interrupt:raise KeyboardInterrupt()
        if maximum==3072:
            self.plan_calls+=1
            if self.invalid_first and 'SYNTHETIC PERSON 0?' in messages[-1]['content']:
                return Response('{}',100,20,.001)
            raw=canonical(dict(nodes=[dict(id='q1',question='Who is the synthetic person?',dependencies={},answer_type='person')],final='q1'))
        else:
            self.decision_calls+=1
            public=json.loads(messages[-1]['content'])
            raw=canonical(dict(assessments=[dict(task_id=t['task_id'],status='insufficient',answer='',refs=[],
                                                entity='synthetic',property='identity',missing_fact='Synthetic identity') for t in public['tasks']],
                               decision=dict(action='retrieve',answer='',refs=[],target_task_ids=[public['tasks'][0]['task_id']],
                                             query='Synthetic identity',reason='Synthetic test only')))
        return Response(raw,100,20,.001)


@unittest.skipUnless((ROOT/'data/final15_manifest.json').exists(), 'Official dataset not prepared; real cohort checks pending')
class RealFinalIdentityTests(unittest.TestCase):
    def test_exactly_fifteen_disjoint_questions_and_seventyfive_states(self):
        questions,manifest=load_final15(check_private=True)
        self.assertEqual(len(questions),15)
        self.assertEqual(sum(len(q['states']) for q in questions),75)
        self.assertEqual(manifest['types'],{'bridge':8,'comparison':7})
        self.assertEqual(manifest['overlap_count'],0)
        self.assertEqual(manifest['model_calls_at_selection'],0)

    def test_final_public_records_have_no_answer_or_gold_fields(self):
        questions,_=load_final15()
        for q in questions:
            self.assertEqual(set(q),{'question_id','question','question_type','split','states'})
            for state in q['states']:self.assertEqual(set(state),{'case_id','evidence'})

    def test_fourteen_question_final_set_is_refused(self):
        questions,_=load_final15()
        with patch('planning_lab.final15.read_jsonl',return_value=questions[:14]):
            with self.assertRaises(ValueError):load_final15()

    def test_final_gold_remains_unadjudicated(self):
        labels=read_jsonl(ROOT/'private/final15_labels.jsonl')
        self.assertEqual(len(labels),75)
        self.assertTrue(all(x['reference_action'] is None and x['semantic_review']=='pending' for x in labels))

    def test_generic_run_cannot_bypass_final_freeze(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                main(['run','--config',str(ROOT/'configs/final15.json'),'--output',td])


class FinalLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.output=self.root/'results'
        (self.root/'private').mkdir();(self.root/'private/final15_labels.jsonl').write_text('synthetic reference labels only')
        self.questions=synthetic_questions();self.registry=read_json(ROOT/'data/split_registry.json')
        self.registry['heldout']=[dict(question_id=q['question_id'],question_sha256=question_digest(q['question'])) for q in self.questions]
        for name,value in [('planning_lab.final15.ROOT',self.root),
                           ('planning_lab.final15.load_final15',lambda **kw:(self.questions,{'synthetic':True}))]:
            p=patch(name,value);p.start();self.addCleanup(p.stop)
        original_read=read_json
        def read_for_run(path):
            return self.registry if Path(path).name=='split_registry.json' else original_read(path)
        p=patch('planning_lab.runner.read_json',side_effect=read_for_run);p.start();self.addCleanup(p.stop)

    def run_final(self,backend=None):
        return run_final15(CONFIG,backend or SyntheticBackend(),self.output,progress=lambda _:None)

    def test_generation_and_two_arms_use_all_fifteen_without_extra_calls_on_resume(self):
        backend=SyntheticBackend();summary=self.run_final(backend)
        self.assertEqual(backend.plan_calls,15)
        self.assertEqual(backend.decision_calls,150)
        self.assertEqual(summary['question_count'],15)
        self.assertEqual(summary['total_model_calls'],165)
        self.assertTrue(summary['execution_complete'])
        self.assertFalse(summary['independent_evaluation_complete'])
        self.run_final(backend)
        self.assertEqual(backend.calls,165)

    def test_failed_question_is_not_replaced_or_dropped(self):
        backend=SyntheticBackend(invalid_first=True);summary=self.run_final(backend)
        self.assertEqual(backend.plan_calls,16)
        self.assertEqual(summary['generation']['plan_statuses'],{'valid':14,'invalid':1})
        self.assertEqual(backend.decision_calls,140)
        self.assertEqual(summary['decision']['recorded_trials'],150)
        self.assertEqual(summary['decision']['arms']['flat']['statuses']['invalid_plan'],5)
        self.assertEqual(len(list((self.output/'plans').glob('*.json'))),15)
        invalid=[read_json(p) for p in (self.output/'plans').glob('*.json') if read_json(p)['status']=='invalid'][0]
        self.assertEqual(len(invalid['trace']),2)

    def test_completed_generation_call_replayed_after_checkpoint_interruption(self):
        backend=SyntheticBackend();original=atomic_json
        def interrupted_write(path,value):
            if Path(path).parent.name=='plans':raise SystemExit('Synthetic interruption after model call')
            return original(path,value)
        with patch('planning_lab.final15.atomic_json',side_effect=interrupted_write):
            with self.assertRaises(SystemExit):self.run_final(backend)
        self.assertEqual(backend.calls,1)
        summary=self.run_final(backend)
        self.assertEqual(backend.plan_calls,15)
        self.assertEqual(summary['total_model_calls'],165)

    def test_unknown_interrupted_usage_is_not_retried(self):
        backend=SyntheticBackend(interrupt=True)
        with self.assertRaises(KeyboardInterrupt):self.run_final(backend)
        backend.interrupt=False
        with self.assertRaises(PendingUsage):self.run_final(backend)
        self.assertEqual(backend.calls,1)

    def test_interrupted_generation_can_be_exported_with_unknown_usage(self):
        import zipfile
        with self.assertRaises(KeyboardInterrupt):self.run_final(SyntheticBackend(interrupt=True))
        target=self.root/'partial.zip';bundle_final15(self.output,target)
        summary=read_json(self.output/'final15_summary.json')
        self.assertEqual(summary['total_model_calls'],1)
        self.assertIsNone(summary['total_tokens'])
        self.assertFalse(summary['execution_complete'])
        self.assertEqual(summary['completed_plan_records'],0)
        with zipfile.ZipFile(target) as z:self.assertTrue(any('/generation_calls/' in n for n in z.namelist()))

    def test_frozen_configuration_changes_are_refused_before_calls(self):
        self.run_final()
        with self.assertRaises(ValueError):freeze_final15(dict(CONFIG,max_output_tokens=1024),self.output)

    def test_reuse_in_new_output_directory_is_refused(self):
        self.run_final()
        with self.assertRaises(ValueError):freeze_final15(CONFIG,self.root/'second_final')

    def test_stored_final_tree_cannot_be_edited(self):
        self.run_final()
        p=next((self.output/'plans').glob('*.json'));row=read_json(p)
        row['plan']['nodes'][0]['question']='Edited after final evaluation'
        atomic_json(p,row)
        with self.assertRaises(ValueError):self.run_final()

    def test_final_bundle_includes_shared_generation_and_all_failures(self):
        import zipfile
        self.run_final(SyntheticBackend(invalid_first=True))
        target=self.root/'final.zip';bundle_final15(self.output,target)
        with zipfile.ZipFile(target) as z:
            self.assertTrue(any('/generation_calls/' in n for n in z.namelist()))
            self.assertEqual(sum('/plans/' in n for n in z.namelist()),15)
            self.assertEqual(sum('/decisions/trials/' in n for n in z.namelist()),150)
            self.assertIsNone(z.testzip())

    def test_unregistered_question_cannot_enter_heldout_runtime(self):
        from planning_lab.final15 import make_final_cases
        plan=dict(nodes=[dict(id='q1',question='Who is the synthetic person?',dependencies={},answer_type='person')],final='q1')
        cases=make_final_cases(self.questions,{q['question_id']:dict(status='valid',plan=plan) for q in self.questions})
        cases[0]['source_question_id']='not-registered'
        with self.assertRaises(ValueError):validate_split(cases,'heldout',self.registry)


if __name__=='__main__':unittest.main()
