"""Paired first-generation direction probe on original max4; no repair or judge."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import zipfile

import decomposition_pilot as pilot
from hotpotqa_operadic_rag.checkpoint import RunStore, atomic_json, digest
from hotpotqa_operadic_rag.config import MODEL_NAME, MODEL_REVISION, RANDOM_SEED
from hotpotqa_operadic_rag.contracts import parse_json_object, validate_plan, expand_typed_plan
from hotpotqa_operadic_rag.decomposition import plan_instructions

ROOT = Path(__file__).resolve().parent
CASE_SHA256 = 'd0d87db293210b6d5bab5fd463160bbb592e9f7251ee43813c41c8f6e97f1ddc'
METHODS = ('baseline', 'direction_template')
DIRECTION_TEMPLATE = '''Directional clause template (S, D, O are symbolic, not entity names):
For "S is D of O", keep the original direction D and the positions of S and O.
If O is the unknown bridge entity: "S is D of which [entity type]?"
If S is the unknown bridge entity: "Which [entity type] is D of O?"
Replace only the unknown entity phrase in that clause; do not move the known entity across D.
Then ask the original final property of the identified entity using its answer slot, preserving units and qualifiers. Do not resolve the unknown entity from memory.'''


def load_cases():
    raw = (ROOT / 'evaluation/direction_probe_cases.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CASE_SHA256:
        raise ValueError('Direction development cases differ from the pinned snapshot.')
    return json.loads(raw)


def messages_for(sample, method):
    if method not in METHODS:
        raise ValueError('Unknown method.')
    system = plan_instructions(sample['question'])
    if method == 'direction_template':
        system += '\n' + DIRECTION_TEMPLATE
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': sample['question']}]


def inspect_output(raw):
    result = {'raw_output': raw, 'plan': None, 'structure_status': 'invalid',
              'structure_error': '', 'expanded_tree': '', 'direction_correctness': 'manual_review_required'}
    try:
        plan = validate_plan(parse_json_object(raw), max_nodes=4)
    except ValueError as exc:
        result['structure_error'] = str(exc)
    else:
        result.update(plan=plan, structure_status='valid', expanded_tree=expand_typed_plan(plan))
    return result


def generate_once(llm, messages):
    return inspect_output(llm.generate(messages, max_new_tokens=3072))


def export_report(store, cases):
    rows = []
    costs = {m: Counter() for m in METHODS}
    statuses = {m: Counter() for m in METHODS}
    structure = {m: Counter() for m in METHODS}
    text = ['# Direction probe: paired first outputs', '',
            'Five development cases; no automatic semantic winner, judge, repair or RAG.',
            'Direction, final target, units and all qualifiers need manual review.', '']
    for index, sample in enumerate(cases, 1):
        record = store.read(sample['question_id'])
        text += [f'## {index}. {sample["question_id"]}', '', sample['question'], '',
                 'Manual reference (not sent to either model call): ' + sample['manual_relation'], '']
        row = {'question_id': sample['question_id'], 'question': sample['question'], 'arms': {}}
        for method in METHODS:
            phase = record['phases'].get(method, {})
            result = phase.get('result', {})
            statuses[method][phase.get('status', 'pending')] += 1
            structure[method][result.get('structure_status', 'not_checked')] += 1
            cost = {k: sum(h.get('telemetry', {}).get(k, 0) for h in phase.get('history', [])) for k in pilot.COST_KEYS}
            costs[method].update(cost)
            row['arms'][method] = {'phase_status': phase.get('status', 'pending'), 'runtime_error': phase.get('error', ''),
                'messages': messages_for(sample, method), 'result': result, 'cost': cost,
                'cost_complete': phase.get('status') == 'observed'}
            text += [f'### {method}', '', 'Phase: ' + phase.get('status', 'pending'),
                'Runtime error: ' + phase.get('error', ''),
                pilot.markdown_code_block(result.get('raw_output', '(no saved output)')), '',
                'Structure: ' + result.get('structure_status', 'not_checked'),
                'Structure error: ' + result.get('structure_error', ''),
                'Expanded tree: ' + result.get('expanded_tree', ''),
                'Manual direction/target/qualifiers/decomposition review: pending.', '']
        rows.append(row)
    summary = {'experiment': 'max4_direction_probe_v1', 'case_count': len(cases),
        'phase_status': {m: dict(v) for m, v in statuses.items()},
        'structure_status': {m: dict(v) for m, v in structure.items()},
        'cost_per_arm': {m: dict(v) for m, v in costs.items()},
        'total_cost': {k: sum(costs[m][k] for m in METHODS) for k in pilot.COST_KEYS},
        'completed_calls': sum(statuses[m]['observed'] for m in METHODS),
        'pending_phases': sum(statuses[m]['pending'] for m in METHODS),
        'semantic_accuracy_measured': False, 'automatic_winner': None,
        'inference_backend': store.manifest['settings']['backend'],
        'scope': 'One first-generation call per arm/case, 10 total; alternating arm order. '
                 'Synthetic development cases and a known failure are not held-out validation. '
                 'Structural validity does not establish correct direction. Core original max4 is unchanged.'}
    directory = store.output.parent
    atomic_json(directory / 'summary.json', summary)
    atomic_json(directory / 'comparison.json', rows)
    (directory / 'review.md').write_text('\n'.join(text), encoding='utf-8')
    archive = directory.with_name(directory.name + '_results.zip')
    temporary = archive.with_suffix('.zip.tmp')
    paths = [directory / n for n in ('summary.json', 'comparison.json', 'review.md')]
    paths += list(store.directory.rglob('*.json'))
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            z.write(path, path.relative_to(directory.parent))
    os.replace(temporary, archive)
    return summary


def run_probe(output_dir, *, report_only=False, model_factory=None):
    fixture = load_cases()
    cases = fixture['cases']
    settings = {'schema_version': 1, 'n_samples': len(cases), 'experiment': 'max4_direction_probe_v1',
        'core_code_sha256': pilot.code_digest(), 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'case_sha256': CASE_SHA256, 'direction_template_sha256': hashlib.sha256(DIRECTION_TEMPLATE.encode()).hexdigest(),
        'backend': 'injected_test' if model_factory else 'LocalQwen', 'model': MODEL_NAME,
        'model_revision': MODEL_REVISION, 'seed': RANDOM_SEED, 'use_4bit': True, 'require_cuda': True,
        'max_input_tokens': 8500, 'intermediate_tokens': 512, 'plan_tokens': 3072, 'max_nodes': 4,
        'calls_per_arm_case': 1, 'repair_calls': 0, 'judge_calls': 0}
    directory = Path(output_dir).expanduser().resolve()
    if report_only and not (directory / 'comparison.csv.state/manifest.json').exists():
        raise ValueError('No existing direction probe to report.')
    store = RunStore(directory / 'comparison.csv', settings, lambda: cases)
    summary = export_report(store, cases)
    if report_only or summary['pending_phases'] == 0:
        return summary
    llm, identity = (model_factory or pilot.create_model)(settings)
    if model_factory is None and identity != fixture['runtime_identity']:
        raise ValueError('Use the same model/library environment as the original max4 run.')
    store.bind_runtime(identity)
    for index, sample in enumerate(cases):
        record = store.read(sample['question_id'])
        order = METHODS if index % 2 == 0 else METHODS[::-1]
        for method in order:
            if method in record['phases']:
                continue
            messages = messages_for(sample, method)
            # Never silently repeat a reserved call after an abrupt exit. On
            # restart only phases never started are run; uncertain costs remain flagged.
            record['phases'][method] = {'status': 'started', 'result': {}, 'history': [],
                'error': 'Reserved invocation; if abruptly interrupted cost/output may be incomplete.'}
            store.write(record)
            print(f'[{index+1}/{len(cases)}] {method}: {sample["question_id"]}', flush=True)
            try:
                pilot.run_phase(store, record, method, lambda: generate_once(llm, messages))
            finally:
                summary = export_report(store, cases)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default=str(ROOT / 'results/max4_direction_probe_v1'))
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    summary = run_probe(args.output_dir, report_only=args.report_only)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary['completed_calls'] != 2 * summary['case_count']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
