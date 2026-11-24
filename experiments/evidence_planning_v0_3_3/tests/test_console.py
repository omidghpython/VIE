"""Console callbacks must not change prompts, actions, costs or saved research results."""
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from planning_lab.console import ConsoleProgress
from planning_lab.common import atomic_json, read_json
from planning_lab import rag_cli, rag_runner as runner, rag_evaluation as evaluation
from planning_lab.rag_retrieval import BM25Retriever, RetrieverFactory
from test_rag import CONFIG, METHODS, ScriptBackend, fixture, plan_record


def without_clock(value):
    if isinstance(value, dict):
        return {k: without_clock(v) for k, v in value.items() if 'seconds' not in k}
    if isinstance(value, list):
        return [without_clock(v) for v in value]
    return value


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.question = fixture()

    def tearDown(self):
        self.temp.cleanup()

    def trial(self, method, backend, directory, observer=None):
        return runner.execute_trial(self.question, method, plan_record(self.question), CONFIG,
            backend, BM25Retriever(self.question['passages']), directory, observer=observer)

    def test_visible_and_silent_execution_have_identical_research_results(self):
        for method in METHODS:
            silent, visible = ScriptBackend(), ScriptBackend()
            expected = self.trial(method, silent, self.root / method / 'silent')
            stream = io.StringIO()
            console = ConsoleProgress(self.root / method / 'visible', stream)
            try:
                actual = self.trial(method, visible, self.root / method / 'visible', console)
            finally:
                console.close()
            self.assertEqual(silent.messages, visible.messages)
            self.assertEqual(without_clock(expected), without_clock(actual))
            for name in ['model_calls', 'retrieval_calls']:
                first = [without_clock(read_json(p)) for p in sorted((self.root / method / 'silent' / name).glob('*.json'))]
                second = [without_clock(read_json(p)) for p in sorted((self.root / method / 'visible' / name).glob('*.json'))]
                self.assertEqual(first, second)
            self.assertIn(' | INFO | [LLM', stream.getvalue())
            self.assertIn('[RETRIEVAL]', stream.getvalue())
            self.assertEqual(stream.getvalue(), (self.root / method / 'visible/console.log').read_text())

    def test_mutating_or_failing_observer_cannot_change_inputs_or_saved_events(self):
        def bad_console(kind, **data):
            for value in data.values():
                if isinstance(value, (dict, list)):
                    value.clear()
            raise OSError('Synthetic broken display')
        first, second = ScriptBackend(), ScriptBackend()
        expected = self.trial('operadic', first, self.root / 'plain')
        actual = self.trial('operadic', second, self.root / 'broken', bad_console)
        self.assertEqual(first.messages, second.messages)
        self.assertEqual(without_clock(expected), without_clock(actual))

    def test_replayed_calls_are_labelled_without_extra_model_or_retrieval_work(self):
        backend = ScriptBackend()
        self.trial('operadic', backend, self.root / 'replay')
        count = len(backend.messages)
        stream = io.StringIO()
        console = ConsoleProgress(stream=stream)
        try:
            with patch.object(BM25Retriever, 'search', side_effect=AssertionError('Repeated retrieval')):
                result = self.trial('operadic', backend, self.root / 'replay', console)
        finally:
            console.close()
        self.assertEqual(result['answer'], 'Bruma')
        self.assertEqual(count, len(backend.messages))
        self.assertIn('REPLAY saved call; no new generation', stream.getvalue())
        self.assertIn('REPLAY saved search', stream.getvalue())

    def test_unknown_usage_and_refused_stop_remain_failures_with_console_enabled(self):
        for mode, status in [('model_error', 'execution_error'), ('reject_support', 'budget_exhausted')]:
            stream = io.StringIO()
            console = ConsoleProgress(stream=stream)
            backend = ScriptBackend(mode)
            try:
                result = self.trial('operadic', backend, self.root / mode, console)
                console('method_completed', method='operadic', result=result)
            finally:
                console.close()
            self.assertEqual(result['status'], status)
            self.assertEqual(result['answer'], '')
            if mode == 'model_error':
                self.assertIsNone(result['costs']['total_tokens'])
                self.assertIn('tokens=unknown', stream.getvalue())
            else:
                self.assertIn('BLOCKED', stream.getvalue())
                self.assertIn('allowed=False', stream.getvalue())

    def test_pause_resume_has_global_question_numbers_and_skips_finished_records(self):
        questions = [fixture('synthetic-one'), fixture('synthetic-two')]
        backend, factory, stream = ScriptBackend(), RetrieverFactory(CONFIG), io.StringIO()
        console = ConsoleProgress(stream=stream)
        try:
            with patch.object(runner, 'load_questions', return_value=questions):
                partial = runner.run_rag(questions, CONFIG, backend, factory, self.root / 'run',
                    max_new_questions=1, progress=lambda _: None, observer=console)
                complete = runner.run_rag(questions, CONFIG, backend, factory, self.root / 'run',
                    max_new_questions=1, progress=lambda _: None, observer=console)
        finally:
            console.close()
        self.assertEqual(partial['recorded_trials'], 3)
        self.assertEqual(complete['recorded_trials'], 6)
        for phrase in ['[1/2]', '[2/2]', 'SESSION PAUSED', 'RUN COMPLETE', 'SKIP: all three']:
            self.assertIn(phrase, stream.getvalue())

    def test_question_setup_failure_is_visible_and_later_questions_continue(self):
        from test_rag_batch import questions, SelectiveFactory
        from planning_lab.common import digest
        qs = questions(2)
        ordered = sorted(qs, key=lambda q: digest([CONFIG['seed'], q['question_id']]))
        factory = SelectiveFactory(ordered[0]['question_id'])
        stream = io.StringIO()
        console = ConsoleProgress(stream=stream)
        try:
            with patch.object(runner, 'load_questions', return_value=qs):
                result = runner.run_rag(qs, CONFIG, ScriptBackend(), factory, self.root/'setup_failure',
                                       progress=lambda _:None, observer=console)
        finally:
            console.close()
        self.assertEqual(result['recorded_trials'], 6)
        self.assertTrue(result['execution_complete'])
        for phrase in ['failure records will be saved', 'retriever_setup_error', '[2/2]', 'RUN COMPLETE']:
            self.assertIn(phrase, stream.getvalue())

    def test_unwritable_console_file_does_not_disable_terminal_or_execution(self):
        stream = io.StringIO()
        with patch('planning_lab.console.logging.FileHandler', side_effect=PermissionError('Synthetic log denial')):
            console = ConsoleProgress(self.root/'blocked_log', stream)
        try:
            result = self.trial('operadic', ScriptBackend(), self.root/'log_denial_trial', console)
        finally:
            console.close()
        self.assertIsNone(console.log_path)
        self.assertEqual(result['status'], 'answered')
        self.assertIn('Console file unavailable', stream.getvalue())

    def test_cli_shows_model_setup_before_trial_progress_and_writes_same_report(self):
        questions = [self.question]
        backend, factory = ScriptBackend(), RetrieverFactory(CONFIG)
        labels = {self.question['question_id']: {'answer': 'Bruma', 'supporting_facts': [['Document 0', 0], ['Document 3', 0]]}}
        config = self.root / 'config.json'
        atomic_json(config, CONFIG)
        output, stream = self.root / 'cli', io.StringIO()
        with patch.object(rag_cli, 'load_questions', return_value=questions), \
             patch.object(runner, 'load_questions', return_value=questions), \
             patch('planning_lab.backend.HFBackend', return_value=backend), \
             patch('planning_lab.rag_retrieval.RetrieverFactory', return_value=factory), \
             patch.object(evaluation, 'references', return_value=labels), \
             contextlib.redirect_stdout(stream):
            rag_cli.main(['run', '--config', str(config), '--output', str(output), '--max-new-questions', '1'])
        log = stream.getvalue()
        self.assertLess(log.index('Loading shared retriever'), log.index('[1/1]'))
        self.assertLess(log.index('with CUDA / NF4'), log.index('[1/1]'))
        self.assertTrue((output / 'RAG_REPORT_FA.txt').is_file())
        self.assertEqual(read_json(output / 'execution_summary.json')['recorded_trials'], 3)
        self.assertIn('Console log:', log)


if __name__ == '__main__':
    unittest.main()
