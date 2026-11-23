"""Question-local experiments with durable per-method and per-OC resume."""
import hashlib
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from .config import (DEFAULT_MAX_INPUT_TOKENS, DEFAULT_MAX_NEW_TOKENS, DEFAULT_N_SAMPLES,
    DEFAULT_OUTPUT, DEFAULT_INTERMEDIATE_TOKENS, DEFAULT_PLAN_TOKENS, DATASET_NAME,
    DATASET_CONFIG, DATASET_SPLIT, RANDOM_SEED, MODEL_NAME, EMBEDDING_MODEL, MODEL_REVISION, EMBEDDING_REVISION,
    MAX_PLAN_NODES, PLAN_ATTEMPTS, HYBRID_ALPHA, TOP_K, MAX_RETRIEVALS, RUN_SCHEMA_VERSION)
from .checkpoint import RunStore, digest
from .data import load_hotpotqa, load_sample_snapshot
from .llm import LocalQwen
from .metrics import reference_answer, answer_metrics, evidence_metrics, squad_f1
from .reporting import print_summary
from .retriever import build_question_retrievers, get_indices
from .methods.standard import run_standard_rag
from .methods.operadic import run_operadic_rag
from .telemetry import TelemetryTracker, activate_tracker
from .utils import configure_logging, set_seed, check_runtime, clear_cuda_cache

LOGGER = logging.getLogger('hotpotqa_operadic_rag')


def source_digest():
    checksum = hashlib.sha256()
    root = Path(__file__).parent
    for path in sorted(root.rglob('*.py')):
        checksum.update(str(path.relative_to(root)).replace('\\', '/').encode())
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def _json_cell(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def results_frame(store):
    rows = []
    for sample in store.samples:
        qid = sample['question_id']
        phases = store.read(qid)['phases']
        row = {'question_id': qid, 'question': sample['question'], 'ground_truth_answer': reference_answer(sample),
               'question_type': sample['type'], 'dataset_split': DATASET_SPLIT}
        for phase, prefix in (('standard','std'), ('operadic','operadic'), ('oc','oc')):
            outcome = phases.get(phase, {})
            row[prefix + '_status'] = outcome.get('status', 'pending')
            row[prefix + '_error'] = outcome.get('error', '')
            row[prefix + '_attempts'] = len(outcome.get('history', []))
            stats = outcome.get('telemetry', {})
            for key in ('retrieval_steps','llm_calls','prompt_tokens','completion_tokens','total_tokens','execution_time_sec'):
                row[prefix + '_' + key] = stats.get(key, 0)
                row[prefix + '_cumulative_' + key] = sum(h.get('telemetry', {}).get(key, 0) for h in outcome.get('history', []))
            result = outcome.get('result', {})
            if phase in ('standard','operadic'):
                for metric in ('f1','em','acc','supporting_fact_coverage_first','supporting_fact_coverage_final','supporting_fact_count','premature_stopping'):
                    row[prefix + '_' + metric] = result.get('metrics', {}).get(metric)
                row[prefix + '_stopped_after_first'] = result.get('stopped_after_first')
                row[prefix + '_evidence_step1_indices'] = _json_cell(get_indices(result.get('evidence_first', [])))
                row[prefix + '_evidence_all_indices'] = _json_cell(get_indices(result.get('evidence_final', [])))
                row[prefix + '_retrieval_trace'] = _json_cell(result.get('retrieval_trace', []))
        a = phases.get('standard', {}).get('result', {})
        b = phases.get('operadic', {}).get('result', {})
        oc = phases.get('oc', {}).get('result', {})
        row.update(answer_std=a.get('answer_std',''), answer_decomposed=b.get('answer_decomposed',''),
                   answer_direct=oc.get('answer_direct',''), plan_json=_json_cell(b.get('plan')),
                   expanded_plan=b.get('expanded_plan',''), semantic_status=b.get('semantic_status','unreviewed'),
                   node_rounds=_json_cell(b.get('node_rounds',[])),
                   decomposition_trace=_json_cell(b.get('decomposition_trace', phases.get('operadic',{}).get('error_details',{}).get('decomposition_trace',[]))),
                   oc_score=oc.get('oc_score'), oc_consistent=oc.get('oc_consistent'), oc_valid=oc.get('oc_valid',False))
        row.update(answer_status=b.get('answer_status', ''), answer_source=b.get('answer_source', ''),
                   reused_nodes=b.get('reused_nodes', 0), targeted_review_calls=b.get('targeted_review_calls', 0),
                   semantic_review_independent=False)
        if not b:
            row['semantic_status'] = phases.get('operadic', {}).get('error_details', {}).get('semantic_status', 'unreviewed')
        for metric in ('f1','em','acc'):
            row['decomposed_' + metric] = row['operadic_' + metric]
            row['direct_' + metric] = oc.get('metrics', {}).get(metric)
        row['operadic_core_time_sec'] = row['operadic_execution_time_sec']
        row['operadic_oc_time_sec'] = row['oc_execution_time_sec']
        row['operadic_total_time_sec'] = row['operadic_core_time_sec'] + row['operadic_oc_time_sec']
        row['retrieval_steps_total_both_methods'] = row['std_retrieval_steps'] + row['operadic_retrieval_steps']
        row['llm_calls_total_both_methods'] = row['std_llm_calls'] + row['operadic_llm_calls'] + row['oc_llm_calls']
        rows.append(row)
    return pd.DataFrame(rows)


def export_csv(store):
    frame = results_frame(store)
    temp = store.output.with_name(store.output.name + '.tmp')
    # Replace only a projection of ALL existing checkpoints; never discard old rows.
    with temp.open('w', encoding='utf-8-sig', newline='') as handle:
        frame.to_csv(handle, index=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, store.output)
    return frame


def _run_phase(store, record, name, function, evaluator=None):
    previous = record['phases'].get(name, {})
    if previous.get('status') == 'completed':
        return
    tracker = TelemetryTracker(name)
    interrupted = None
    outcome = {'status': 'failed', 'error': '', 'result': {}}
    try:
        with activate_tracker(tracker):
            result = function(tracker)
        if evaluator:
            result['metrics'] = evaluator(result)
        outcome.update(status='completed', result=result)
    except (Exception, KeyboardInterrupt) as exc:
        outcome.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                       error=f'{type(exc).__name__}: {exc}', error_details=getattr(exc, 'details', {}))
        clear_cuda_cache()
        LOGGER.error('%s / %s: %s', record['question_id'], name, outcome['error'])
        if isinstance(exc, KeyboardInterrupt):
            interrupted = exc
    finally:
        outcome['telemetry'] = tracker.as_dict()
        outcome['history'] = previous.get('history', []) + [{
            'status': outcome['status'], 'error': outcome['error'], 'telemetry': tracker.as_dict(),
            'error_details': outcome.get('error_details', {}), 'time_utc': datetime.now(timezone.utc).isoformat()}]
        record['phases'][name] = outcome
        store.write(record)
        export_csv(store)
    if interrupted is not None:
        raise interrupted


def _oc_result(llm, question, core):
    direct = llm.answer(question, core['evidence_final'])
    valid = bool(direct.strip() and core['answer_decomposed'].strip())
    # The original F1 formula/0.5 threshold is used when both answers exist.
    score = squad_f1(direct, core['answer_decomposed']) if valid else None
    return {'answer_direct': direct, 'oc_score': score,
            'oc_consistent': bool(score >= 0.5) if valid else None, 'oc_valid': valid}


def run_experiment(n_samples=DEFAULT_N_SAMPLES, use_4bit=True,
                   max_input_tokens=DEFAULT_MAX_INPUT_TOKENS, max_new_tokens=DEFAULT_MAX_NEW_TOKENS,
                   output_csv=DEFAULT_OUTPUT, require_cuda=True,
                   intermediate_tokens=DEFAULT_INTERMEDIATE_TOKENS, plan_tokens=DEFAULT_PLAN_TOKENS,
                   samples_json=None):
    configure_logging()
    if type(n_samples) is not int or n_samples % 2 or not 30 <= n_samples <= 50:
        raise ValueError('Choose an even sample count from 30 to 50.')
    if any(type(n) is not int or n < 1 for n in (max_input_tokens,max_new_tokens,intermediate_tokens,plan_tokens)):
        raise ValueError('Token budgets must be positive integers.')
    snapshot = load_sample_snapshot(samples_json, n_samples) if samples_json else None
    settings = dict(schema_version=RUN_SCHEMA_VERSION, code_sha256=source_digest(), n_samples=n_samples,
                    seed=RANDOM_SEED, model=MODEL_NAME, embedding_model=EMBEDDING_MODEL,
                    model_revision=MODEL_REVISION, embedding_revision=EMBEDDING_REVISION,
                    dataset=DATASET_NAME, dataset_config=DATASET_CONFIG, dataset_split=DATASET_SPLIT,
                    use_4bit=use_4bit, require_cuda=require_cuda, max_input_tokens=max_input_tokens,
                    max_new_tokens=max_new_tokens, intermediate_tokens=intermediate_tokens, plan_tokens=plan_tokens,
                    max_nodes=MAX_PLAN_NODES, plan_attempts=PLAN_ATTEMPTS, top_k=TOP_K,
                    max_retrievals=MAX_RETRIEVALS, alpha=HYBRID_ALPHA, context_scope='per_question_10',
                    sample_snapshot_sha256=digest(snapshot) if snapshot is not None else None)
    store = RunStore(output_csv, settings, lambda: snapshot if snapshot is not None else load_hotpotqa(n_samples))
    export_csv(store)  # Recover CSV if interrupted after JSON checkpoint but before export.
    if store.all_complete():
        frame = results_frame(store)
        frame.attrs['run_complete'] = True
        print_summary(frame, str(store.output))
        LOGGER.info('All phases were already completed; no model or retriever loaded.')
        return frame
    set_seed()
    check_runtime(require_cuda=require_cuda)
    pending_retrieval = [s for s in store.samples if not all(store.completed(s['question_id'], p) for p in ('standard','operadic'))]
    retrievers = build_question_retrievers(pending_retrieval) if pending_retrieval else {}
    llm = LocalQwen(use_4bit=use_4bit, max_input_tokens=max_input_tokens, max_new_tokens=max_new_tokens,
                    intermediate_tokens=intermediate_tokens, plan_tokens=plan_tokens)
    old_identity = store.manifest.get('runtime_identity') or {}
    encoder_revision = old_identity.get('embedding_revision')
    if retrievers:
        encoder = next(iter(retrievers.values())).encoder
        try:
            encoder_revision = encoder[0].auto_model.config._commit_hash
        except (AttributeError, TypeError, IndexError, KeyError):
            encoder_revision = None
    store.bind_runtime({'qwen_revision': getattr(getattr(getattr(llm, 'model', None), 'config', None), '_commit_hash', None),
                        'embedding_revision': encoder_revision})
    for order, sample in enumerate(store.samples, 1):
        LOGGER.info("[%d/%d] %s (%s)", order, len(store.samples), sample["question_id"], sample["type"])
        qid, question, gold = sample['question_id'], sample['question'], reference_answer(sample)
        record = store.read(qid)
        def evaluate(result, key):
            return {**answer_metrics(result[key], gold), **evidence_metrics(result, sample['supporting_facts'])}
        _run_phase(store, record, 'standard',
                   lambda tracker: run_standard_rag(question, retrievers[qid], llm, tracker),
                   lambda result: evaluate(result, 'answer_std'))
        _run_phase(store, record, 'operadic',
                   lambda tracker: run_operadic_rag(question, retrievers[qid], llm, tracker),
                   lambda result: evaluate(result, 'answer_decomposed'))
        if record['phases']['operadic']['status'] == 'completed':
            core = record['phases']['operadic']['result']
            _run_phase(store, record, 'oc', lambda tracker: _oc_result(llm, question, core),
                       lambda result: answer_metrics(result['answer_direct'], gold))
    frame = export_csv(store)
    frame.attrs['run_complete'] = store.all_complete()
    print_summary(frame, str(store.output))
    if frame.attrs['run_complete']:
        LOGGER.info('Experiment completed. Results: %s', store.output)
    else:
        LOGGER.error('Experiment has failed/incomplete phases. Existing successes are saved; rerun to retry unfinished phases.')
    return frame
