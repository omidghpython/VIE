import copy
import json
import tempfile
import unittest
from pathlib import Path

from planning_lab.backend import Response
from planning_lab.common import ROOT, atomic_json, canonical, digest, read_json, read_jsonl, verify_baseline, write_jsonl
from planning_lab.contracts import parse_decision
from planning_lab.dataset import validate_case, validate_split, register_holdout, context_sentences
from planning_lab.evaluation import export_review, score_reviews
from planning_lab.policy import structural_observation, invalidate_descendants
from planning_lab.prompts import messages, payload, task_view, assert_matched_pair
from planning_lab.runner import run_experiment, trial_id, validate_config
from planning_lab.reporting import export_report, bundle_results

CASES = read_jsonl(ROOT/'data/development_cases.jsonl')
CASE = next(c for c in CASES if c['structure_valid'] and len(c['plan']['nodes']) > 1 and c['evidence'])
OTHER = next(c for c in CASES if c['structure_valid'] and c['source_question_id'] != CASE['source_question_id'] and c['evidence'])
CONFIG = read_json(ROOT/'configs/development.json')
REGISTRY = read_json(ROOT/'data/split_registry.json')


def reply_from_payload(public, action='retrieve'):
    refs = [public['evidence'][0]['ref']] if public['evidence'] else []
    assessments = [dict(task_id=t['task_id'], status='supported' if action == 'stop' else 'insufficient',
                        answer='Test value' if action == 'stop' else '', refs=refs if action == 'stop' else [],
                        entity='Test entity', property='Test property', missing_fact='Test missing fact')
                   for t in public['tasks']]
    return dict(assessments=assessments, decision=dict(action=action, answer='Test value' if action == 'stop' else '',
                  refs=refs if action == 'stop' else [], target_task_ids=[public['tasks'][0]['task_id']] if action == 'retrieve' else [],
                  query='Test missing fact' if action == 'retrieve' else '', reason='Synthetic software test only'))


class FakeBackend:
    identity = {'backend': 'synthetic_test', 'test_only': True}
    load_seconds = 0.0
    def __init__(self, mode='normal'):
        self.mode = mode
        self.calls = 0
    def count_tokens(self, msg):
        return 9000 if self.mode == 'input_limit' else 100
    def check_context(self, prompt, output):
        pass
    def generate(self, msg, maximum, seed):
        self.calls += 1
        if self.mode == 'error':
            raise RuntimeError('Synthetic generation failure')
        text = 'broken JSON' if self.mode == 'bad_json' else canonical(reply_from_payload(json.loads(msg[1]['content'])))
        return Response(text, 100, 20, 0.01, self.mode == 'output_limit')


def small_tree():
    plan = {'nodes': [
        {'id':'q1','question':'Who directed Example Film?', 'dependencies':{}, 'answer_type':'person'},
        {'id':'q2','question':'Where was {{q1}} born?', 'dependencies':{'q1':'person'}, 'answer_type':'place'},
        {'id':'q3','question':'What country contains {{q2}}?', 'dependencies':{'q2':'place'}, 'answer_type':'place'}], 'final':'q3'}
    return dict(CASE, plan=plan, plan_sha256=digest(plan))


class DataIsolationTests(unittest.TestCase):
    def test_baseline_source_unchanged(self):
        self.assertEqual(len(verify_baseline()['unchanged_files']), 20)

    def test_all_forty_kept_with_invalid_cases(self):
        self.assertEqual(len(CASES), 200)
        self.assertEqual(len({c['source_question_id'] for c in CASES}), 40)
        self.assertEqual(sum(c['structure_valid'] for c in CASES), 185)
        validate_split(CASES, 'development', REGISTRY)

    def test_all_public_evidence_is_exact_source_text(self):
        samples = read_json(ROOT/'private/original_samples.json')
        sources = {s['id']: {e['ref']:e for e in context_sentences(s)} for s in samples}
        for case in CASES:
            for evidence in case['evidence']:
                self.assertEqual(evidence, sources[case['source_question_id']][evidence['ref']])

    def test_only_structure_differs_across_every_pair(self):
        for case in CASES:
            if case['structure_valid']:
                assert_matched_pair(case)
                self.assertEqual(messages(case,'structured')[0], messages(case,'flat')[0])

    def test_flat_has_no_explicit_graph_or_unresolved_slots(self):
        view = payload(CASE,'flat')
        self.assertIsNone(view['structure'])
        self.assertNotIn('{{q', canonical(view))
        self.assertNotIn('dependencies', canonical(view))
        self.assertEqual(set(view), {'question','tasks','evidence','structure'})

    def test_gold_or_condition_in_runtime_schema_rejected(self):
        for key in ['answer','supporting_facts','condition','visible_gold_coverage','reference_action']:
            case = dict(CASE, **{key:'LEAK_SENTINEL'})
            with self.assertRaises(ValueError): validate_case(case)

    def test_prompt_allowlist_never_serializes_extra_private_fields(self):
        dirty = dict(CASE, answer='PRIVATE_SENTINEL', condition='PRIVATE_SENTINEL')
        self.assertNotIn('PRIVATE_SENTINEL', canonical(messages(dirty,'structured')))

    def test_relabel_development_as_heldout_rejected(self):
        case = dict(CASE,split='heldout')
        with self.assertRaises(ValueError): validate_split([case],'heldout',REGISTRY)

    def test_new_id_same_development_question_rejected(self):
        case = dict(CASE, split='heldout', source_question_id='new-id')
        with self.assertRaises(ValueError): validate_split([case],'heldout',REGISTRY)

    def test_tree_changes_rejected_even_after_rehash(self):
        case = copy.deepcopy(CASE)
        case['plan']['nodes'][0]['question'] += ' Changed.'
        case['plan_sha256'] = digest(case['plan'])
        with self.assertRaises(ValueError): validate_split([case],'development',REGISTRY)

    def test_duplicate_cases_rejected(self):
        with self.assertRaises(ValueError): validate_split([CASE,CASE],'development',REGISTRY)

    def test_duplicate_evidence_refs_rejected(self):
        case = dict(CASE,evidence=CASE['evidence']+[CASE['evidence'][0]])
        with self.assertRaises(ValueError): validate_case(case)

    def test_holdout_registration_rejects_overlap_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'in.jsonl';out=Path(td)/'out.json'
            write_jsonl(path,[dict(question_id='new',question=CASE['question'])])
            with self.assertRaises(ValueError): register_holdout(path,out)
            rows=[dict(question_id='new',question='A genuinely new test question?')]*2
            write_jsonl(path,rows)
            with self.assertRaises(ValueError): register_holdout(path,out)
            write_jsonl(path,rows[:1])
            self.assertEqual(register_holdout(path,out),1)
            self.assertEqual(read_json(out)['role'],'candidate_heldout')


class DecisionAndPolicyTests(unittest.TestCase):
    def test_valid_decision_with_supported_negative_answer(self):
        result=reply_from_payload(payload(CASE,'structured'),'stop')
        result['assessments'][0]['answer']='No'
        self.assertEqual(parse_decision(canonical(result),CASE)['assessments'][0]['answer'],'No')

    def test_fabricated_citation_rejected(self):
        result=reply_from_payload(payload(CASE,'structured'),'stop')
        result['assessments'][0]['refs']=['not-a-source']
        with self.assertRaises(ValueError): parse_decision(canonical(result),CASE)

    def test_empty_source_sentence_preserved_but_not_valid_support(self):
        case=copy.deepcopy(CASE);case['evidence'][0]['text']=''
        validate_case(case)
        result=reply_from_payload(payload(case,'structured'),'stop')
        with self.assertRaises(ValueError): parse_decision(canonical(result),case)

    def test_empty_evidence_cannot_have_cited_stop(self):
        empty=dict(CASE,evidence=[])
        result=reply_from_payload(payload(empty,'structured'),'stop')
        with self.assertRaises(ValueError): parse_decision(canonical(result),empty)

    def test_missing_task_and_duplicate_json_keys_rejected(self):
        result=reply_from_payload(payload(CASE,'flat'))
        result['assessments'].pop()
        with self.assertRaises(ValueError): parse_decision(canonical(result),CASE)
        with self.assertRaises(ValueError): parse_decision('{"decision":{},"decision":{}}',CASE)

    def test_unknown_target_and_contradictory_action_rejected(self):
        result=reply_from_payload(payload(CASE,'flat'))
        result['decision']['target_task_ids']=['unknown']
        with self.assertRaises(ValueError): parse_decision(canonical(result),CASE)
        result=reply_from_payload(payload(CASE,'flat'),'stop')
        result['decision']['query']='extra retrieval'
        with self.assertRaises(ValueError): parse_decision(canonical(result),CASE)

    def test_structural_observer_does_not_rewrite_model_decision(self):
        case=small_tree();result=reply_from_payload(payload(case,'structured'),'stop')
        _,graph=task_view(case)
        leaf=next(e['producer'] for e in graph['edges'] if not any(x['consumer']==e['producer'] for x in graph['edges']))
        row=next(r for r in result['assessments'] if r['task_id']==leaf)
        row.update(status='insufficient',answer='',refs=[])
        before=copy.deepcopy(result)
        observation=structural_observation(case,result)
        self.assertEqual(result,before)
        self.assertTrue(observation['model_stop_without_structural_closure'])
        self.assertEqual(observation['target_task_id'],leaf)
        self.assertEqual(sum(e['structural_status']=='blocked' for e in observation['events']),2)

    def test_budget_exhaustion_never_labeled_success(self):
        case=small_tree();result=reply_from_payload(payload(case,'structured'))
        obs=structural_observation(case,result,remaining_retrievals=0)
        self.assertEqual((obs['suggested_action'],obs['reason']),('abstain','budget_exhausted'))

    def test_invalidation_reaches_all_descendants_only(self):
        graph={'edges':[dict(producer='a',consumer='b'),dict(producer='b',consumer='c'),dict(producer='x',consumer='c')]}
        self.assertEqual(invalidate_descendants(graph,{'a'}),{'a','b','c'})
        self.assertNotIn('x',invalidate_descendants(graph,{'a'}))


class RunnerTests(unittest.TestCase):
    def run_at(self,path,backend,cases=None,config=None,cap=None):
        return run_experiment(cases or [CASE],config or CONFIG,backend,path,max_new_calls=cap,progress=lambda _:None)

    def test_one_call_per_arm_resume_is_free(self):
        with tempfile.TemporaryDirectory() as td:
            backend=FakeBackend();summary=self.run_at(td,backend)
            self.assertEqual(backend.calls,2)
            self.assertTrue(summary['execution_complete'])
            self.run_at(td,backend)
            self.assertEqual(backend.calls,2)
            self.assertEqual(summary['arms']['flat']['total_tokens'],120)

    def test_session_cap_preserves_complete_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            backend=FakeBackend();summary=self.run_at(td,backend,[CASE,OTHER],cap=3)
            self.assertEqual(backend.calls,2)
            self.assertFalse(summary['execution_complete'])
            self.assertEqual(summary['arms']['structured']['recorded_trials'],1)
            self.assertEqual(summary['arms']['flat']['recorded_trials'],1)

    def test_invalid_plans_kept_without_calls(self):
        invalid=next(c for c in CASES if not c['structure_valid'])
        with tempfile.TemporaryDirectory() as td:
            backend=FakeBackend();summary=self.run_at(td,backend,[invalid])
            self.assertEqual(backend.calls,0)
            self.assertEqual(summary['arms']['structured']['statuses'],{'invalid_plan':1})

    def test_input_limit_has_zero_calls_and_no_truncation(self):
        with tempfile.TemporaryDirectory() as td:
            backend=FakeBackend('input_limit');summary=self.run_at(td,backend)
            self.assertEqual(backend.calls,0)
            self.assertEqual(summary['arms']['flat']['statuses'],{'input_rejected':1})

    def test_output_limit_cost_is_retained(self):
        with tempfile.TemporaryDirectory() as td:
            summary=self.run_at(td,FakeBackend('output_limit'))
            self.assertEqual(summary['arms']['flat']['statuses'],{'output_limit':1})
            self.assertEqual(summary['arms']['flat']['total_tokens'],120)

    def test_bad_json_is_not_semantic_uncertainty(self):
        with tempfile.TemporaryDirectory() as td:
            summary=self.run_at(td,FakeBackend('bad_json'))
            self.assertEqual(summary['arms']['flat']['statuses'],{'invalid_response':1})
            self.assertIsNone(summary['premature_stopping'])

    def test_failed_call_unknown_usage_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            summary=self.run_at(td,FakeBackend('error'))
            self.assertEqual(summary['arms']['flat']['llm_calls'],1)
            self.assertIsNone(summary['arms']['flat']['total_tokens'])
            self.assertEqual(summary['arms']['flat']['unknown_usage_trials'],1)

    def test_changed_configuration_cannot_resume(self):
        with tempfile.TemporaryDirectory() as td:
            self.run_at(td,FakeBackend())
            config=dict(CONFIG,max_output_tokens=1024)
            with self.assertRaises(ValueError): self.run_at(td,FakeBackend(),config=config)

    def test_changed_backend_cannot_resume(self):
        with tempfile.TemporaryDirectory() as td:
            self.run_at(td,FakeBackend());backend=FakeBackend();backend.identity={'backend':'other'}
            with self.assertRaises(ValueError): self.run_at(td,backend)

    def test_inflight_never_automatically_rerun(self):
        with tempfile.TemporaryDirectory() as td:
            backend=FakeBackend();self.run_at(td,backend)
            path=Path(td)/'trials'/(trial_id(CASE,'flat')+'.json')
            record=read_json(path);record['status']='inflight';atomic_json(path,record)
            with self.assertRaises(RuntimeError): self.run_at(td,backend)
            self.assertEqual(backend.calls,2)

    def test_nonpositive_budget_and_retries_disallowed(self):
        for change in [dict(max_input_tokens=0),dict(max_model_calls_per_trial=2)]:
            with self.assertRaises(ValueError): validate_config(dict(CONFIG,**change))


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'results';self.review=self.root/'review'
        run_experiment([CASE],CONFIG,FakeBackend(),self.output,progress=lambda _:None)
        export_review(self.output,self.review,ROOT/'private/development_labels.jsonl')
        self.packet_path=self.review/'review_packets.jsonl';self.mapping=self.review/'private_mapping.json'

    def finalized(self):
        rows=read_jsonl(self.packet_path)
        for row in rows:
            row['review'].update(final=True,reviewer_id='synthetic-test-reviewer',state_sufficient=False,
                                 decision_acceptable=True,target_acceptable=True,query_acceptable=True,
                                 binding_correct=True,cited_claims=0,supported_cited_claims=0,
                                 required_claims=0,supported_cited_required_claims=0)
        return rows

    def test_no_arm_or_condition_in_review_packet(self):
        row=read_jsonl(self.packet_path)[0]
        self.assertNotIn('arm',row)
        self.assertNotIn('condition',row)
        self.assertNotIn('structure',row)

    def test_pending_review_never_becomes_zero_accuracy(self):
        result=score_reviews(self.output,self.packet_path,self.mapping)
        self.assertIsNone(result['metrics']['flat']['reviewed_decision_accuracy'])
        self.assertFalse(result['evaluation_complete'])

    def test_reviewed_metrics_and_zero_citation_denominator(self):
        write_jsonl(self.packet_path,self.finalized())
        result=score_reviews(self.output,self.packet_path,self.mapping)
        self.assertEqual(result['metrics']['structured']['reviewed_decision_accuracy'],1)
        self.assertIsNone(result['metrics']['structured']['citation_faithfulness'])
        self.assertTrue(result['evaluation_complete'])

    def test_partial_reviews_have_explicit_denominators(self):
        rows=self.finalized();rows[0]['review']['final']=False;write_jsonl(self.packet_path,rows)
        result=score_reviews(self.output,self.packet_path,self.mapping)
        self.assertFalse(result['evaluation_complete'])
        self.assertEqual(sum(m['reviewed_trials'] for m in result['metrics'].values()),1)

    def test_conflicting_state_labels_must_be_adjudicated(self):
        rows=self.finalized();rows[0]['review']['state_sufficient']=True;write_jsonl(self.packet_path,rows)
        with self.assertRaises(ValueError): score_reviews(self.output,self.packet_path,self.mapping)

    def test_changed_reference_or_trial_rejected(self):
        rows=self.finalized();rows[0]['reference']['answer']='altered';write_jsonl(self.packet_path,rows)
        with self.assertRaises(ValueError): score_reviews(self.output,self.packet_path,self.mapping)

    def test_review_export_never_overwrites_annotations(self):
        with self.assertRaises(ValueError): export_review(self.output,self.review,ROOT/'private/development_labels.jsonl')

    def test_portable_report_and_bundle_preserve_raw_trials(self):
        import zipfile
        export_report(self.output)
        result=bundle_results(self.output,self.root/'bundle.zip')
        with zipfile.ZipFile(result['bundle']) as z:
            self.assertEqual(sum('/trials/' in n for n in z.namelist()),2)
            self.assertIsNone(z.testzip())
            self.assertTrue(any(n.endswith('report_FA.md') for n in z.namelist()))

    def test_impossible_citation_counts_rejected(self):
        rows=self.finalized();rows[0]['review'].update(cited_claims=1,supported_cited_claims=2)
        write_jsonl(self.packet_path,rows)
        with self.assertRaises(ValueError): score_reviews(self.output,self.packet_path,self.mapping)


if __name__=='__main__':
    unittest.main()
