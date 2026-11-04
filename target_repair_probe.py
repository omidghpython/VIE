"""One live repair of a fixed saved first output; no regeneration or model judge."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

import decomposition_pilot as pilot
from hotpotqa_operadic_rag.checkpoint import RunStore, atomic_json, digest
from hotpotqa_operadic_rag.config import MODEL_NAME, MODEL_REVISION, RANDOM_SEED
from hotpotqa_operadic_rag.contracts import parse_json_object, validate_plan, expand_typed_plan
from hotpotqa_operadic_rag.decomposition import plan_instructions, value_target_check

ROOT = Path(__file__).resolve().parent
FIXTURE_SHA256 = 'fc94126c986637e8b4cb6ca1863ef1bf57ec5853cf45c2e251e8553f94066970'
REPAIR_INSTRUCTION = '''Repair the complete tree to satisfy all three requirements together:
1. The final question and answer_type must return the name/value requested by the original question, not merely verify a candidate or ask for another property.
2. final must identify the root: no other node may depend on it. Every non-final node must feed exactly one consumer on a path to final. Rebuild dependencies as needed; changing only final is not enough.
3. Preserve every original relation and qualifier on the same entity, including qualifiers used to select the answer. Do not drop a qualifier or replace checking that qualifier with listing a broader property.
Return the complete JSON tree in the original schema, with at most four nodes. Do not answer the question or invent facts.'''


def load_fixture():
    raw = (ROOT / 'evaluation/target_repair_probe_fixture.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        raise ValueError('Saved input differs from the pinned original output.')
    fixture = json.loads(raw)
    plan = validate_plan(parse_json_object(fixture['first_raw_output']), max_nodes=4)
    if value_target_check(fixture['question'], plan)['status'] != 'mismatch':
        raise ValueError('The saved input must have the intended target mismatch.')
    return fixture


def repair_messages(fixture):
    plan = validate_plan(parse_json_object(fixture['first_raw_output']), max_nodes=4)
    check = value_target_check(fixture['question'], plan)
    return [{'role': 'system', 'content': plan_instructions(fixture['question'])},
            {'role': 'user', 'content': fixture['question'] + '\nTree with target mismatch:\n' +
             fixture['first_raw_output'] + '\nDetected error: ' + ' '.join(check['errors']) +
             '\n' + REPAIR_INSTRUCTION}]


def inspect_output(raw, question):
    result = {'raw_output': raw, 'plan': None, 'structure_status': 'invalid',
              'structure_error': '', 'target_check': {'status': 'not_checked', 'errors': []},
              'expanded_tree': '', 'semantic_correctness': 'not_established',
              'qualifier_preservation': 'manual_review_required'}
    try:
        plan = validate_plan(parse_json_object(raw), max_nodes=4)
    except ValueError as exc:
        result['structure_error'] = str(exc)
    else:
        result.update(plan=plan, structure_status='valid',
                      target_check=value_target_check(question, plan),
                      expanded_tree=expand_typed_plan(plan))
    return result


def single_repair(llm, messages, fixture):
    raw = llm.generate(messages, max_new_tokens=3072)
    return inspect_output(raw, fixture['question'])


def export_report(store, fixture, messages):
    record = store.read(fixture['question_id'])
    phase = record['phases'].get('repair', {})
    result = phase.get('result', {})
    cost = {key: sum(h.get('telemetry', {}).get(key, 0) for h in phase.get('history', []))
            for key in pilot.COST_KEYS}
    summary = {'experiment': 'target_repair_probe_v2', 'question_id': fixture['question_id'],
        'phase_status': phase.get('status', 'pending'), 'runtime_error': phase.get('error', ''),
        'structure_status': result.get('structure_status', 'not_checked'),
        'target_status': result.get('target_check', {}).get('status', 'not_checked'),
        'semantic_correctness': 'not_established', 'qualifier_preservation': 'manual_review_required',
        'inference_backend': store.manifest['settings']['backend'], 'current_cost': cost,
        'current_cost_complete': phase.get('status') == 'observed',
        'historical_repair_cost_excluded_from_current': fixture['previous_repair_tokens'],
        'scope': 'One saved question; one new repair only. No generation of first tree, judge, retrieval or answer. '
                 'Structure/target compatibility do not establish meaning or general improvement.'}
    directory = store.output.parent
    atomic_json(directory / 'summary.json', summary)
    atomic_json(directory / 'messages.json', messages)
    atomic_json(directory / 'source_fixture.json', fixture)
    blocks = ['# Single saved-tree repair probe', '', fixture['question'], '',
        'Historical first output (unchanged):', pilot.markdown_code_block(fixture['first_raw_output']), '',
        'Historical repair v1 (reference only; NOT sent to the model):',
        pilot.markdown_code_block(fixture['previous_repair_raw_output']),
        'Historical structure error: ' + fixture['previous_repair_error'], '',
        'New repair v2:', pilot.markdown_code_block(result.get('raw_output', '(no saved output)')), '',
        'Phase: ' + summary['phase_status'], 'Runtime error: ' + summary['runtime_error'],
        'Structure: ' + summary['structure_status'], 'Structure error: ' + result.get('structure_error', ''),
        'Target: ' + summary['target_status'],
        'Target errors: ' + json.dumps(result.get('target_check', {}).get('errors', [])), '',
        'Expanded tree:', result.get('expanded_tree', ''), '',
        'Manual review REQUIRED: Does final return the original requested entity/value? '
        'Are all relations and qualifiers preserved on that same entity? '
        'Does each node contribute necessary information rather than repeat or rename the original request?', '',
        'No automatic semantic success verdict is assigned. One case cannot establish general improvement.', '',
        'Current cost (historical calls excluded):', pilot.markdown_code_block(json.dumps(cost, indent=2)), '']
    (directory / 'review.md').write_text('\n'.join(blocks), encoding='utf-8')
    archive = directory.with_name(directory.name + '_results.zip')
    temporary = archive.with_suffix('.zip.tmp')
    paths = [directory / name for name in ('summary.json', 'messages.json', 'source_fixture.json', 'review.md')]
    paths += list(store.directory.rglob('*.json'))
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            z.write(path, path.relative_to(directory.parent))
    os.replace(temporary, archive)
    return summary


def run_probe(output_dir, *, report_only=False, model_factory=None):
    fixture = load_fixture()
    messages = repair_messages(fixture)
    settings = {'schema_version': 1, 'n_samples': 1, 'experiment': 'target_repair_probe_v2',
        'core_code_sha256': pilot.code_digest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fixture_sha256': FIXTURE_SHA256, 'messages_sha256': digest(messages),
        'backend': 'injected_test' if model_factory else 'LocalQwen',
        'model': MODEL_NAME, 'model_revision': MODEL_REVISION, 'seed': RANDOM_SEED,
        'use_4bit': True, 'require_cuda': True, 'max_input_tokens': 8500,
        'intermediate_tokens': 512, 'plan_tokens': 3072, 'max_nodes': 4, 'new_repair_calls': 1}
    directory = Path(output_dir).expanduser().resolve()
    if report_only and not (directory / 'probe.csv.state/manifest.json').exists():
        raise ValueError('No existing probe to report.')
    sample = {k: fixture[k] for k in ('question_id', 'question')}
    store = RunStore(directory / 'probe.csv', settings, lambda: [sample])
    record = store.read(sample['question_id'])
    if report_only or 'repair' in record['phases']:
        # Never automatically spend another call after failure or interruption.
        return export_report(store, fixture, messages)
    llm, identity = (model_factory or pilot.create_model)(settings)
    if model_factory is None and identity != fixture['runtime_identity']:
        raise ValueError('Use the same model/library environment as the saved run; runtime identity differs.')
    store.bind_runtime(identity)
    # Persist before inference, so an abrupt process exit cannot silently cause
    # another attempt on a normal restart. This is not a completed repair.
    record['phases']['repair'] = {'status': 'started', 'result': {}, 'history': [],
        'error': 'An invocation was reserved. If the process exited abruptly, cost/output may be incomplete.'}
    store.write(record)
    try:
        pilot.run_phase(store, record, 'repair', lambda: single_repair(llm, messages, fixture))
    finally:
        summary = export_report(store, fixture, messages)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default=str(ROOT / 'results/target_repair_probe_v2'))
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    summary = run_probe(args.output_dir, report_only=args.report_only)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary['phase_status'] != 'observed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
