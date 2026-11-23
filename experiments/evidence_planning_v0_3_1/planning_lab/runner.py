from __future__ import annotations
from collections import Counter
import contextlib
import os
from pathlib import Path
import time
from .common import ROOT, atomic_json, canonical, digest, read_json, source_identity, verify_baseline
from .contracts import parse_decision
from .dataset import validate_split
from .policy import structural_observation
from .prompts import messages, assert_matched_pair, SYSTEM


def validate_config(config):
    expected = {'schema_version', 'role', 'model', 'model_revision', 'allow_model_download', 'seed',
                'max_input_tokens', 'max_output_tokens', 'max_model_calls_per_trial', 'protocol'}
    if set(config) != expected or config['schema_version'] != 1:
        raise ValueError('Unexpected configuration fields')
    if config['protocol'] != 'one_step_structure_ablation_v1':
        raise ValueError('Wrong protocol')
    if config['role'] not in {'development', 'heldout'}:
        raise ValueError('Invalid role')
    if config['model'] != 'Qwen/Qwen2.5-7B-Instruct' or config['model_revision'] != 'a09a35458c702b33eeacc393d103063234e8bc28':
        raise ValueError('This version freezes the accepted model identity')
    if type(config['allow_model_download']) is not bool or type(config['seed']) is not int:
        raise ValueError('Invalid model options')
    for key in ['max_input_tokens', 'max_output_tokens', 'max_model_calls_per_trial']:
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError('Budgets must be positive integers')
    if config['max_model_calls_per_trial'] != 1:
        raise ValueError('One decision call per arm/state; no repair/retry in this protocol')


def trial_id(case, arm):
    return digest([case['case_id'], arm])[:32]


@contextlib.contextmanager
def output_lock(output):
    path = output / '.run.lock'
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError('Output is locked. Check for an active process before recovering a stale lock.') from exc
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def ordered_pairs(cases, seed):
    # Balanced crossover: each adjacent state reverses the first arm; both arms use same case seed.
    ordered = sorted(cases, key=lambda c: digest([seed, c['case_id']]))
    for i, case in enumerate(ordered):
        arms = ['structured', 'flat'] if i % 2 == 0 else ['flat', 'structured']
        yield case, arms


def run_experiment(cases, config, backend, output, *, max_new_calls=None, progress=print):
    validate_config(config)
    if not cases:
        raise ValueError('Empty experiment')
    if max_new_calls is not None and (type(max_new_calls) is not int or max_new_calls < 2):
        raise ValueError('Session call cap must allow at least one complete pair')
    registry = read_json(ROOT / 'data/split_registry.json')
    validate_split(cases, config['role'], registry)
    baseline = verify_baseline()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with output_lock(output):
        identity = dict(protocol=config['protocol'], config=config, dataset_sha256=digest(cases),
                        source_sha256=source_identity(), prompt_sha256=digest(SYSTEM),
                        baseline_zip_sha256=baseline['baseline_zip_sha256'], backend=backend.identity)
        manifest_path = output / 'manifest.json'
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest['identity'] != identity:
                raise ValueError('Resume refused: source, data, prompt, config or runtime identity differs.')
        else:
            manifest = dict(identity=identity, question_count=len({c['source_question_id'] for c in cases}),
                            case_count=len(cases), expected_trials=len(cases) * 2,
                            costs='Decision calls only; historical decomposition costs are separate.',
                            retrieval_executed=False, model_load_seconds=getattr(backend, 'load_seconds', None),
                            state_level_claim='model predictions; independent review pending',
                            role=config['role'], evaluation_scope='controlled one-step decisions; not full RAG')
            atomic_json(manifest_path, manifest)
            atomic_json(output / 'runtime_cases.json', cases)
        new_calls = 0
        for case, arms in ordered_pairs(cases, config['seed']):
            paths = {arm: output / 'trials' / (trial_id(case, arm) + '.json') for arm in arms}
            existing = {arm: read_json(path) for arm, path in paths.items() if path.exists()}
            if any(row['status'] == 'inflight' for row in existing.values()):
                raise RuntimeError('Interrupted inflight call: usage is unresolved. Automatic rerun is forbidden.')
            pending = [arm for arm in arms if arm not in existing]
            if not pending:
                continue
            if case['structure_valid'] and max_new_calls is not None and new_calls + len(pending) > max_new_calls:
                break
            common_hash = assert_matched_pair(case) if case['structure_valid'] else None
            for arm in pending:
                started = time.perf_counter()
                record = dict(trial_id=trial_id(case, arm), case_id=case['case_id'],
                              source_question_id=case['source_question_id'], arm=arm, role=case['split'],
                              plan_sha256=case['plan_sha256'], common_input_sha256=common_hash,
                              status='pending', action=None, raw_output=None, parsed=None, error=None,
                              usage=dict(llm_calls=0, retrieval_calls=0, prompt_tokens=0, completion_tokens=0,
                                         total_tokens=0, generation_seconds=0.0), independent_semantic_review='pending')
                path = paths[arm]
                if not case['structure_valid']:
                    record['status'] = 'invalid_plan'
                    record['error'] = 'Stored max4 structure invalid; no repair, no hidden fallback or model call.'
                else:
                    msg = messages(case, arm)
                    record['messages'] = msg
                    record['messages_sha256'] = digest(msg)
                    try:
                        input_length = backend.count_tokens(msg)
                        record['input_tokens_measured'] = input_length
                        if input_length > config['max_input_tokens']:
                            raise ValueError('Input budget exceeded; evidence was not truncated')
                        backend.check_context(input_length, config['max_output_tokens'])
                    except Exception as exc:
                        record['status'] = 'input_rejected'
                        record['error'] = f'{type(exc).__name__}: {exc}'
                    else:
                        record['status'] = 'inflight'
                        record['usage'].update(llm_calls=1, prompt_tokens=input_length,
                                               completion_tokens=None, total_tokens=None, generation_seconds=None)
                        atomic_json(path, record)  # Durable before costly work; resume cannot silently repeat it.
                        new_calls += 1
                        try:
                            response = backend.generate(msg, config['max_output_tokens'], config['seed'])
                            if response.prompt_tokens != input_length:
                                raise RuntimeError('Tokenization changed between budget check and generation')
                            record['raw_output'] = response.text
                            record['usage'].update(prompt_tokens=response.prompt_tokens,
                                                   completion_tokens=response.completion_tokens,
                                                   total_tokens=response.prompt_tokens + response.completion_tokens,
                                                   generation_seconds=response.generation_seconds)
                            if response.output_limit:
                                record['status'] = 'output_limit'
                                record['error'] = 'Output reached cap without EOS; incomplete decision retained as failure.'
                            else:
                                try:
                                    parsed = parse_decision(response.text, case)
                                except (ValueError, TypeError, KeyError) as exc:
                                    record['status'] = 'invalid_response'
                                    record['error'] = str(exc)
                                else:
                                    record.update(status='completed', parsed=parsed, action=parsed['decision']['action'],
                                                  structural_observer=structural_observation(case, parsed))
                        except KeyboardInterrupt:
                            record['status'] = 'interrupted_usage_unknown'
                            record['error'] = 'Call was interrupted; output token usage unknown. No automatic retry.'
                            record['elapsed_seconds'] = time.perf_counter() - started
                            atomic_json(path, record)
                            raise
                        except Exception as exc:
                            record['status'] = 'model_error'
                            record['error'] = f'{type(exc).__name__}: {exc}'
                record['elapsed_seconds'] = time.perf_counter() - started
                atomic_json(path, record)
                progress(f"{case['case_id']} {arm}: {record['status']}")
        summary = summarize_run(output)
        atomic_json(output / 'summary.json', summary)
        return summary


def summarize_run(output):
    output = Path(output)
    manifest = read_json(output / 'manifest.json')
    rows = [read_json(path) for path in sorted((output / 'trials').glob('*.json'))]
    arms = {}
    for arm in ['structured', 'flat']:
        selected = [r for r in rows if r['arm'] == arm]
        unknown = [r for r in selected if r['usage']['total_tokens'] is None]
        arms[arm] = dict(recorded_trials=len(selected), statuses=dict(Counter(r['status'] for r in selected)),
                         action_counts=dict(Counter(r['action'] for r in selected if r['action'])),
                         llm_calls=sum(r['usage']['llm_calls'] for r in selected), retrieval_calls=0,
                         known_total_tokens=sum(r['usage']['total_tokens'] or 0 for r in selected),
                         unknown_usage_trials=len(unknown),
                         total_tokens=None if unknown else sum(r['usage']['total_tokens'] for r in selected),
                         known_generation_seconds=sum(r['usage']['generation_seconds'] or 0 for r in selected),
                         generation_seconds=None if any(r['usage']['generation_seconds'] is None for r in selected)
                         else sum(r['usage']['generation_seconds'] for r in selected),
                         elapsed_seconds=sum(r.get('elapsed_seconds', 0) for r in selected))
    return dict(protocol=manifest['identity']['protocol'], role=manifest['role'], backend=manifest['identity']['backend'],
                execution_complete=len(rows) == manifest['expected_trials'] and all(r['status'] != 'inflight' for r in rows),
                expected_trials=manifest['expected_trials'], recorded_trials=len(rows), arms=arms,
                independent_evaluation_complete=False, live_retrieval_executed=False,
                answer_accuracy=None, citation_faithfulness=None, premature_stopping=None,
                warning='Decision predictions are not evaluation labels. No full-RAG result or generalization claim.')
