"""Recorded-path checks for the new scheduler, without inventing a new result.

Usage: python check_frontier_fix.py FIX_SOURCE EXTRACTED_V03_RESULTS OUTPUT_JSON
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile

source, results, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(source.resolve()))
from planning_lab.common import read_json
from planning_lab.rag_runner import _execute_trial, freeze_rag, load_questions
from planning_lab.rag_methods import retrieval_target


class Backend:
    def __init__(self, rows):
        self.rows, self.index = rows, 0

    def count_tokens(self, messages):
        row = self.rows[self.index]
        assert row['request']['messages'] == messages
        self.index += 1
        return row['prompt_tokens']

    def check_context(self, length, maximum):
        pass

    def generate(self, *args, **kwargs):
        raise AssertionError('New model inference forbidden in recorded-path checks')


class Retriever:
    def __init__(self, passages):
        self.passages = passages

    def search(self, *args, **kwargs):
        raise AssertionError('A changed query cannot reuse or invent a saved ranking')


questions = {q['question_id']: q for q in load_questions('development')}
config = read_json(results / 'RAG_LOCK.json')['identity']['config']
report = dict(fresh_model_calls=0, fresh_retrieval_calls=0, final15_used=False,
              changed_query_live_result='pending', unchanged_recorded_paths=[])
for path in sorted((results / 'trials').glob('*.json')):
    saved = read_json(path)
    qid, method = saved['question_id'], saved['method']
    question = questions[qid]
    plan = read_json(results / 'plans' / (qid + '.json'))
    calls = results / 'calls' / qid / method
    rows = [read_json(p) for p in sorted((calls / 'model_calls').glob('*.json'))]
    with tempfile.TemporaryDirectory() as td:
        replay = Path(td) / 'calls'
        shutil.copytree(calls, replay)
        backend = Backend(rows)
        actual = _execute_trial(question, method, plan, config, backend, Retriever(question['passages']), replay)
    if method == 'operadic' and saved['status'] == 'budget_exhausted':
        decisions = [e for e in actual['events'] if e['kind'] == 'controller_decision' and e['action'] == 'retrieve']
        assert [e['target_node'] for e in decisions] == ['q1', 'q2']
        assert decisions[1]['query'] == 'Did Maheen Zia edit films?'
        assert actual['status'] == 'execution_error'
        assert actual['error'] == 'ValueError: Retrieval replay request changed.'
        assert backend.index == 4
        report['changed_path'] = dict(question_id=qid, original_targets=['q1', 'q1'],
            new_targets=['q1', 'q2'], second_query=decisions[1]['query'],
            prefix_model_calls_replayed=4, reused_changed_query_ranking=False,
            outcome='Replay deliberately refused at the changed second query; no patched model answer claimed.')
    else:
        for key in ['answer', 'status', 'citations', 'citation_status', 'costs', 'details', 'evidence_final']:
            assert actual[key] == saved[key], (qid, method, key)
        report['unchanged_recorded_paths'].append(dict(question_id=qid, method=method,
            model_calls_replayed=backend.index, answer=saved['answer'], status=saved['status']))

with tempfile.TemporaryDirectory() as td:
    old_output = Path(td)
    shutil.copyfile(results / 'RAG_LOCK.json', old_output / 'RAG_LOCK.json')
    try:
        freeze_rag(config, list(questions.values()), old_output)
    except ValueError as exc:
        assert str(exc) == 'Source, dataset, settings or references changed; resume refused'
        report['old_source_output_resume_refused'] = True
    else:
        raise AssertionError('Changed source resumed a previous experiment')

output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
