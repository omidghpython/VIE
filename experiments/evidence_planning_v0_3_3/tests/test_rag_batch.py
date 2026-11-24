"""Batch fault isolation with synthetic questions/model and real CPU BM25."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from planning_lab.common import atomic_json, digest, read_json
from planning_lab import rag_runner as runner, rag_evaluation as evaluation
from planning_lab.rag_retrieval import RetrieverFactory
from test_rag import CONFIG, ScriptBackend, fixture


class FailFirstModelCall(ScriptBackend):
    def __init__(self):
        super().__init__()
        self.fail_next = True

    def generate(self, messages, maximum, seed):
        if self.fail_next:
            self.fail_next = False
            self.messages.append(messages)
            raise RuntimeError('Synthetic per-call backend failure with unknown completion usage')
        return super().generate(messages, maximum, seed)


class SelectiveFactory:
    def __init__(self, failed_id=None):
        self.inner = RetrieverFactory(CONFIG)
        self.identity = self.inner.identity
        self.failed_id = failed_id
        self.calls = []

    def __call__(self, passages):
        qid = passages[0]['title']
        self.calls.append(qid)
        if qid == self.failed_id:
            raise RuntimeError('Synthetic per-question index setup failure')
        return self.inner(passages)


def questions(count):
    rows = []
    for i in range(count):
        q = fixture('synthetic-batch-' + str(i))
        q['question'] += ' [synthetic case ' + str(i) + ']'
        q['passages'][0]['title'] = q['question_id']
        rows.append(q)
    return rows


class RagBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / 'results'

    def tearDown(self):
        self.temp.cleanup()

    def test_all_40_continue_after_method_setup_budget_invalid_and_empty_failures(self):
        qs = questions(40)
        ordered = sorted(qs, key=lambda q: digest([CONFIG['seed'], q['question_id']]))
        ordered[2]['structure_valid'] = False
        ordered[3]['plan_debit']['llm_calls'] = CONFIG['max_llm_calls']
        factory = SelectiveFactory(ordered[1]['question_id'])
        backend = FailFirstModelCall()
        standard = runner.METHODS['standard']

        def sometimes_empty(question, *args):
            if question == ordered[4]['question']:
                return dict(answer='', status='abstained', citations_native=[], evidence_final=[], details={})
            return standard(question, *args)

        with patch.object(runner, 'load_questions', return_value=qs), patch.dict(runner.METHODS, standard=sometimes_empty):
            summary = runner.run_rag(qs, CONFIG, backend, factory, self.output, progress=lambda _: None)
            calls_before, setups_before = len(backend.messages), list(factory.calls)
            resumed = runner.run_rag(qs, CONFIG, backend, factory, self.output, progress=lambda _: None)
        self.assertTrue(summary['execution_complete'])
        self.assertEqual(summary['recorded_trials'], 120)
        rows = [read_json(p) for p in (self.output/'trials').glob('*.json')]
        by_key = {(r['question_id'], r['method']): r for r in rows}
        self.assertEqual(len(by_key), 120)
        for q in qs:
            self.assertTrue(all((q['question_id'], m) in by_key for m in runner.METHODS))
        first = by_key[(ordered[0]['question_id'], 'standard')]
        self.assertEqual(first['status'], 'execution_error')
        self.assertEqual(first['costs']['llm_calls'], 1)
        self.assertIsNone(first['costs']['total_tokens'])
        self.assertEqual(by_key[(ordered[0]['question_id'], 'max4')]['status'], 'answered')
        for method in runner.METHODS:
            failed = by_key[(ordered[1]['question_id'], method)]
            self.assertEqual(failed['status'], 'retriever_setup_error')
            self.assertEqual(failed['failure_stage'], 'retriever_setup')
            self.assertIn('Synthetic per-question index', failed['error'])
            self.assertEqual(failed['costs']['total_tokens'], 0)
            self.assertEqual(failed['costs']['retrieval_calls'], 0)
            self.assertEqual(by_key[(ordered[-1]['question_id'], method)]['status'], 'answered')
        for method in ['max4', 'operadic']:
            self.assertEqual(by_key[(ordered[2]['question_id'], method)]['status'], 'invalid_plan')
            self.assertEqual(by_key[(ordered[3]['question_id'], method)]['status'], 'budget_exhausted')
        self.assertEqual(by_key[(ordered[4]['question_id'], 'standard')]['status'], 'abstained')
        self.assertEqual(len(backend.messages), calls_before)
        self.assertEqual(factory.calls, setups_before)
        self.assertEqual(resumed, summary)
        self.assertIsNone(summary['actual_total_tokens'])
        reference = {q['question_id']: dict(answer='Bruma', supporting_facts=[
            [q['passages'][0]['title'], 0], ['Document 3', 0]]) for q in qs}
        with patch.object(evaluation, 'references', return_value=reference):
            report = evaluation.report_rag(self.output)
        for method, values in report['metrics'].items():
            self.assertEqual(values['recorded_questions'], 40)
            self.assertEqual(sum(values['statuses'].values()), 40)
            self.assertAlmostEqual(values['answer_accuracy'], 37/40)
        self.assertFalse((runner.ROOT/'data/final15_usage.json').exists())

    def test_saved_setup_failure_resumes_pending_methods_without_retrying_setup(self):
        qs = questions(1)
        factory = SelectiveFactory(qs[0]['question_id'])
        backend = ScriptBackend()
        original_write = runner.atomic_json
        written = []

        def interrupt_on_second_trial(path, data):
            if Path(path).parent.name == 'trials':
                if written:
                    raise OSError('Synthetic inability to persist a result')
                written.append(path)
            return original_write(path, data)

        with patch.object(runner, 'load_questions', return_value=qs):
            with patch.object(runner, 'atomic_json', side_effect=interrupt_on_second_trial):
                with self.assertRaises(OSError):
                    runner.run_rag(qs, CONFIG, backend, factory, self.output, progress=lambda _: None)
            self.assertEqual(len(list((self.output/'trials').glob('*.json'))), 1)
            result = runner.run_rag(qs, CONFIG, backend, factory, self.output, progress=lambda _: None)
        self.assertEqual(len(factory.calls), 1)
        self.assertEqual(result['recorded_trials'], 3)
        self.assertEqual(len(backend.messages), 0)
        self.assertTrue(result['execution_complete'])

    def test_explicit_interruption_is_not_swallowed(self):
        q = questions(1)[0]

        def interrupt(passages):
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            runner.prepare_retriever(q, interrupt, self.output)
        setup = read_json(self.output/'retriever_setup'/(q['question_id']+'.json'))
        self.assertEqual(setup['status'], 'interrupted')
        self.assertIsNotNone(setup['attempt_seconds'][0])
        self.assertFalse((self.output/'trials').exists())

    def test_source_or_config_integrity_failure_still_stops_before_calls(self):
        qs = questions(1)
        backend = ScriptBackend()
        factory = SelectiveFactory()
        with patch.object(runner, 'load_questions', return_value=qs):
            runner.freeze_rag(CONFIG, qs, self.output)
            with self.assertRaisesRegex(ValueError, 'resume refused'):
                runner.run_rag(qs, dict(CONFIG, max_llm_calls=23), backend, factory,
                               self.output, progress=lambda _: None)
        self.assertEqual(backend.messages, [])
        self.assertEqual(factory.calls, [])

    def test_hard_interrupted_setup_time_remains_unknown_after_resume(self):
        qs = questions(1)
        atomic_json(self.output/'retriever_setup'/(qs[0]['question_id']+'.json'),
                    dict(status='running', attempt_seconds=[None], shared_across_methods=True))
        with patch.object(runner, 'load_questions', return_value=qs):
            result = runner.run_rag(qs, CONFIG, ScriptBackend(), SelectiveFactory(),
                                    self.output, progress=lambda _: None)
        self.assertTrue(result['execution_complete'])
        self.assertIsNone(result['shared_retriever_setup_seconds'])


if __name__ == '__main__':
    unittest.main()
