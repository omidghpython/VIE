"""Audit recorded v0.3 calls without model inference or fresh retrieval.

Usage: python audit_debug.py SOURCE EXTRACTED_RAG_RESULTS OUTPUT_JSON
The source must be the original v0.3 release, not the patched controller.
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

source, results, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(source.resolve()))
from planning_lab.common import digest, file_digest, read_json, verify_baseline
from planning_lab.rag_runner import _execute_trial, load_questions

lock = read_json(results / 'RAG_LOCK.json')
identity = lock['identity']
assert digest(identity) == lock['identity_sha256']
questions = read_json(results / 'runtime_questions.json')
assert digest(questions) == identity['questions_sha256']
assert questions == load_questions('development')
assert len(questions) == 40
assert not (source / 'data/final15_usage.json').exists()
paths = sorted((source / 'planning_lab').glob('*.py')) + [source / 'run.py']
windows_hash = digest({str(p.relative_to(source)).replace('/', '\\'): file_digest(p) for p in paths})
assert windows_hash == identity['source_sha256']
assert file_digest(source / 'run_rag.py') == identity['entrypoint_sha256']
assert verify_baseline()['baseline_zip_sha256'] == identity['baseline_sha256']
assert file_digest(source / 'private/development_labels.jsonl') == identity['reference_labels_sha256']
manifest = read_json(source / 'PACKAGE_MANIFEST.json')
assert all(file_digest(source / p) == h for p, h in manifest['files'].items())
by_id = {q['question_id']: q for q in questions}


class RecordedBackend:
    def __init__(self, rows):
        self.rows, self.next_index = rows, 0

    def count_tokens(self, messages):
        row = self.rows[self.next_index]
        assert row['request']['messages'] == messages
        self.next_index += 1
        return row['prompt_tokens']

    def check_context(self, length, maximum):
        pass

    def generate(self, *args, **kwargs):
        raise AssertionError('A replay must never generate a new model response')


class RecordedRetriever:
    def __init__(self, passages):
        self.passages = passages

    def search(self, *args, **kwargs):
        raise AssertionError('A replay must never execute a new retrieval query')


audit = dict(source_windows_sha256=windows_hash, package_files_verified=len(manifest['files']),
             unchanged_baseline_files=len(verify_baseline()['unchanged_files']),
             development_questions_verified=40, fresh_model_calls=0, fresh_retrieval_calls=0,
             final15_used=False, trials=[])
for trial_path in sorted((results / 'trials').glob('*.json')):
    saved = read_json(trial_path)
    qid, method = saved['question_id'], saved['method']
    question = by_id[qid]
    plan = read_json(results / 'plans' / (qid + '.json'))
    assert plan['plan'] == question['frozen_plan']
    assert plan['budget_debit'] == question['plan_debit']
    assert digest(plan['plan']) == plan['plan_sha256']
    calls = results / 'calls' / qid / method
    model_rows = [read_json(p) for p in sorted((calls / 'model_calls').glob('*.json'))]
    retrieval_rows = [read_json(p) for p in sorted((calls / 'retrieval_calls').glob('*.json'))]
    for row in model_rows + retrieval_rows:
        assert row['status'] == 'completed'
        assert row['request_sha256'] == digest(row['request'])
    for row in retrieval_rows:
        for passage in row['hits']:
            corpus_entry = question['passages'][passage['index']]
            assert {k: passage[k] for k in corpus_entry} == corpus_entry
            assert set(passage) - set(corpus_entry) <= {'dense_score', 'bm25_score', 'hybrid_score'}
    with tempfile.TemporaryDirectory() as td:
        replay_calls = Path(td) / 'calls'
        shutil.copytree(calls, replay_calls)
        backend = RecordedBackend(model_rows)
        replayed = _execute_trial(question, method, plan, identity['config'], backend,
                                  RecordedRetriever(question['passages']), replay_calls)
    expected = {k: v for k, v in saved.items() if k in replayed and k != 'execution_seconds'}
    actual = {k: v for k, v in replayed.items() if k in expected}
    assert expected == actual, (qid, method, [k for k in expected if expected[k] != actual[k]])
    assert backend.next_index == len(model_rows)
    audit['trials'].append(dict(question_id=qid, method=method, status=saved['status'],
        answer=saved['answer'], error=saved.get('error'), costs=saved['costs'],
        exact_replay=True, model_calls=len(model_rows), retrieval_calls=len(retrieval_rows)))
summary = read_json(results / 'execution_summary.json')
audit['actual_llm_calls'] = sum(t['model_calls'] for t in audit['trials'])
audit['actual_retrieval_calls'] = sum(t['retrieval_calls'] for t in audit['trials'])
audit['actual_total_tokens'] = sum(t['costs']['total_tokens'] for t in audit['trials'])
for key in ['actual_llm_calls', 'actual_retrieval_calls', 'actual_total_tokens']:
    assert audit[key] == summary[key]
audit['execution_complete'] = summary['execution_complete']
output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in audit.items() if k != 'trials'}, indent=2))
print('Exact trial replays:', len(audit['trials']))
