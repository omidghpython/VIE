"""Retrieval scheduling regressions; synthetic model, real CPU BM25.

These tests do not establish that the model will accept sufficient evidence.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from planning_lab.backend import Response
from planning_lab.common import ROOT, canonical, digest, read_json
from planning_lab.rag_methods import retrieval_target
from planning_lab.rag_retrieval import BM25Retriever
from planning_lab.rag_runner import execute_trial


PLAN = {'nodes': [
    {'id': 'q1', 'question': 'Did River edit films?', 'answer_type': 'boolean', 'dependencies': {}},
    {'id': 'q2', 'question': 'Did Valley edit films?', 'answer_type': 'boolean', 'dependencies': {}},
    {'id': 'q3', 'question': 'Which director also edited films, River ({{q1}}) or Valley ({{q2}})?',
     'answer_type': 'person', 'dependencies': {'q1': 'boolean', 'q2': 'boolean'}}], 'final': 'q3'}


class UnresolvedBackend:
    def __init__(self):
        self.calls = 0

    def count_tokens(self, messages):
        return 100

    def check_context(self, prompt, output):
        pass

    def generate(self, messages, maximum, seed):
        self.calls += 1
        text = messages[-1]['content']
        assert text.startswith('Answer Node using only Evidence')
        node = text.split('\nNode:\n', 1)[1].split('\nAnswer type:', 1)[0]
        assert node in ['Did River edit films?', 'Did Valley edit films?']
        return Response(canonical({'answer': '', 'refs': [], 'need': node}), 100, 20, .001)


class FrontierTests(unittest.TestCase):
    def test_untried_ready_branch_precedes_retry(self):
        self.assertEqual(retrieval_target(PLAN, {}, {})['id'], 'q1')
        self.assertEqual(retrieval_target(PLAN, {}, {'q1': 1})['id'], 'q2')
        self.assertEqual(retrieval_target(PLAN, {}, {'q1': 1, 'q2': 1})['id'], 'q1')

    def test_counts_do_not_make_a_blocked_child_ready(self):
        target = retrieval_target(PLAN, {}, {'q1': 9, 'q2': 8})
        self.assertEqual(target['id'], 'q2')
        self.assertEqual(retrieval_target(PLAN, {'q1': {}, 'q2': {}}, {})['id'], 'q3')
        self.assertIsNone(retrieval_target(PLAN, {'q1': {}, 'q2': {}, 'q3': {}}, {}))

    def test_only_unresolved_branch_can_be_retried(self):
        self.assertEqual(retrieval_target(PLAN, {'q2': {}}, {'q1': 1})['id'], 'q1')

    def test_equal_counts_retain_downstream_priority_and_do_not_modify_plan(self):
        plan = copy.deepcopy(PLAN)
        plan['nodes'].insert(2, dict(id='bridge', question='Is {{q2}} relevant?',
                                   answer_type='boolean', dependencies={'q2': 'boolean'}))
        plan['nodes'][-1]['dependencies'] = {'q1': 'boolean', 'bridge': 'boolean'}
        plan['nodes'][-1]['question'] = 'Which director, River ({{q1}}) or Valley ({{bridge}})?'
        before = copy.deepcopy(plan)
        self.assertEqual(retrieval_target(plan, {}, {})['id'], 'q2')
        self.assertEqual(retrieval_target(plan, {}, {'q2': 1})['id'], 'q1')
        self.assertEqual(plan, before)

    def test_real_retrieval_rotates_branches_stays_bounded_and_replays(self):
        config = dict(read_json(ROOT / 'configs/rag_development.json'), retriever='bm25')
        passages = [dict(index=i, title='Document ' + str(i), sentence_ids=[0],
                         sentences=['River Valley films background ' + str(i)],
                         text='River Valley films background ' + str(i)) for i in range(10)]
        question = dict(question_id='synthetic-frontier', role='development',
                        question='Which director also edited films, River or Valley?', passages=passages)
        plan_record = dict(plan=PLAN, plan_sha256=digest(PLAN), status='valid',
                           budget_debit={'llm_calls': 2, 'total_tokens': 100})
        backend = UnresolvedBackend()
        retriever = BM25Retriever(passages)
        with tempfile.TemporaryDirectory() as td:
            result = execute_trial(question, 'operadic', plan_record, config, backend, retriever, Path(td))
            with patch.object(retriever, 'search', side_effect=AssertionError('Duplicate retrieval')):
                resumed = execute_trial(question, 'operadic', plan_record, config, backend, retriever, Path(td))
        decisions = [e for e in result['events'] if e['kind'] == 'controller_decision']
        retrieved = [e for e in decisions if e['action'] == 'retrieve']
        self.assertEqual([e['target_node'] for e in retrieved], ['q1', 'q2'])
        self.assertEqual(retrieved[1]['query'], 'Did Valley edit films?')
        self.assertEqual(retrieved[1]['frontier_attempts'], {'q1': 1, 'q2': 0})
        self.assertEqual(len([e for e in result['events'] if e['kind'] == 'retrieval_executed']), 2)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(result['error'], 'retrieval_calls')
        self.assertEqual(result['answer'], '')
        self.assertEqual(result['costs']['retrieval_calls'], 2)
        self.assertEqual(result['costs']['llm_calls'], 4)
        self.assertEqual(result['costs']['charged_llm_calls'], 6)
        self.assertFalse(any(e['action'] == 'stop' for e in decisions))
        self.assertTrue(any(e['kind'] == 'node_blocked' and e['node_id'] == 'q3' for e in result['events']))
        self.assertFalse(any(e['kind'] == 'node_inputs' and e['node_id'] == 'q3' for e in result['events']))
        self.assertEqual(decisions[-1], dict(kind='controller_decision', action='budget_exhausted', reason='retrieval_calls'))
        self.assertEqual(resumed['events'], result['events'])
        self.assertEqual(resumed['costs'], result['costs'])
        self.assertEqual(backend.calls, 4)


if __name__ == '__main__':
    unittest.main()
