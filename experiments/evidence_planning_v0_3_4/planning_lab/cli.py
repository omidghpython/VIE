import argparse
import json
from pathlib import Path
from .common import ROOT, atomic_json, digest, read_json, read_jsonl, verify_baseline, file_digest
from .dataset import build_development, validate_split, register_holdout
from .prompts import assert_matched_pair, messages
from .runner import run_experiment, validate_config
from .evaluation import export_review, score_reviews
from .reporting import export_report, bundle_results
from .final15 import load_final15, freeze_final15, run_final15, final_report, bundle_final15


def main(argv=None):
    parser = argparse.ArgumentParser(description='Frozen max4: development40 and heldout final15, v0.2')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('verify', help='Verify baseline and development data; no model loading')
    sub.add_parser('prepare-development', help='Rebuild deterministic data from frozen source archives')
    preview = sub.add_parser('preview', help='Write exactly the two paired prompts; no model calls')
    preview.add_argument('--case-id', required=True)
    preview.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('run', help='Run one decision per state/arm using local Qwen on CUDA')
    run.add_argument('--cases', type=Path, default=ROOT/'data/development_cases.jsonl')
    run.add_argument('--config', type=Path, default=ROOT/'configs/development.json')
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--max-new-calls', type=int, default=20, help='Session cap; pause between complete pairs (default 20)')
    run.add_argument('--all', action='store_true', help='Run all remaining trials instead of a 20-call session')
    review = sub.add_parser('export-review', help='Export arm-blinded independent-review packets')
    review.add_argument('--results', type=Path, required=True)
    review.add_argument('--output', type=Path, required=True)
    review.add_argument('--labels', type=Path, default=None)
    score = sub.add_parser('score', help='Score finalized independent reviews; no inference')
    score.add_argument('--results', type=Path, required=True)
    score.add_argument('--reviews', type=Path, required=True)
    score.add_argument('--mapping', type=Path, required=True)
    heldout = sub.add_parser('register-holdout', help='Reject development/duplicate questions; register only')
    heldout.add_argument('--input', type=Path, required=True)
    heldout.add_argument('--output', type=Path, required=True)
    report = sub.add_parser('report', help='Export a readable Persian report and decision CSV')
    report.add_argument('--results', type=Path, required=True)
    bundle = sub.add_parser('bundle-results', help='Create a portable ZIP of saved run outputs')
    bundle.add_argument('--results', type=Path, required=True)
    bundle.add_argument('--output', type=Path, required=True)
    sub.add_parser('verify-final15', help='Check the 15 fixed unseen questions and overlap; no inference')
    for name in ['freeze-final15','run-final15']:
        p=sub.add_parser(name,help='Freeze settings' if name=='freeze-final15' else 'Generate fixed max4 plans and run final15 decisions')
        p.add_argument('--config',type=Path,default=ROOT/'configs/final15.json')
        p.add_argument('--output',type=Path,default=ROOT/'results/final15_v1')
    p=sub.add_parser('report-final15',help='Report shared generation and decision costs separately')
    p.add_argument('--results',type=Path,required=True)
    p=sub.add_parser('bundle-final15',help='Package complete final15 outputs, including generation costs')
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare-development':
        # Explicit rebuild only; no generation, no tree repairs.
        result = build_development()
    elif args.command == 'verify':
        baseline = verify_baseline()
        cases = read_jsonl(ROOT/'data/development_cases.jsonl')
        manifest = read_json(ROOT/'data/development_manifest.json')
        registry = read_json(ROOT/'data/split_registry.json')
        validate_split(cases, 'development', registry)
        if digest(cases) != manifest['cases_sha256']:
            raise ValueError('Development cases differ from construction manifest')
        if digest(read_jsonl(ROOT/'private/development_labels.jsonl')) != manifest['labels_sha256']:
            raise ValueError('Private labels changed')
        if digest(registry['development']) != manifest['questions_sha256']:
            raise ValueError('Frozen question registry changed')
        for case in cases:
            if case['structure_valid']:
                assert_matched_pair(case)
        result = dict(baseline=baseline['baseline'], unchanged_source_files=len(baseline['unchanged_files']),
                      questions=40, cases=len(cases), valid_questions=37, invalid_questions=3,
                      matched_input_pairs=sum(c['structure_valid'] for c in cases),
                      model_calls=0, retrieval_calls=0)
        final_questions, final_manifest=load_final15(check_private=True)
        result['heldout_final_questions']=len(final_questions)
        result['heldout_states']=final_manifest['state_count']
        result['known_exposure_overlap']=0
        package_manifest = ROOT/'PACKAGE_MANIFEST.json'
        if package_manifest.exists():
            for rel, expected in read_json(package_manifest)['files'].items():
                if file_digest(ROOT/rel) != expected:
                    raise ValueError('Package file differs: ' + rel)
            result['package_verified'] = True
    elif args.command == 'preview':
        cases = read_jsonl(ROOT/'data/development_cases.jsonl')
        matches = [c for c in cases if c['case_id'] == args.case_id]
        if not matches or not matches[0]['structure_valid']:
            raise ValueError('Unknown case or invalid frozen tree')
        result = {arm: messages(matches[0], arm) for arm in ['structured', 'flat']}
        if args.output.exists():
            raise ValueError('Preview output already exists')
        atomic_json(args.output, result)
        result = dict(output=str(args.output), model_calls=0)
    elif args.command == 'run':
        config = read_json(args.config)
        cases = read_jsonl(args.cases)
        validate_config(config)
        if config['role']=='heldout':
            raise ValueError('Use run-final15 for heldout evaluation; generic run is development-only')
        validate_split(cases, config['role'], read_json(ROOT/'data/split_registry.json'))
        verify_baseline()
        from .backend import HFBackend
        backend = HFBackend(config)
        result = run_experiment(cases, config, backend, args.output,
                                max_new_calls=None if args.all else args.max_new_calls)
    elif args.command == 'export-review':
        role=read_json(args.results/'manifest.json')['role']
        labels=args.labels or ROOT/('private/final15_labels.jsonl' if role=='heldout' else 'private/development_labels.jsonl')
        result = export_review(args.results, args.output, labels)
    elif args.command == 'score':
        result = score_reviews(args.results, args.reviews, args.mapping)
    elif args.command == 'report':
        result = export_report(args.results)
    elif args.command == 'bundle-results':
        result = bundle_results(args.results,args.output)
    elif args.command == 'verify-final15':
        q,m=load_final15(check_private=True)
        result=dict(questions=len(q),types=m['types'],states=m['state_count'],known_exposure_overlap=0,
                    model_calls=0,source_url=m['source_url'],scope=m['novelty_scope'])
    elif args.command in {'freeze-final15','run-final15'}:
        config=read_json(args.config)
        identity=freeze_final15(config,args.output)
        if args.command=='freeze-final15':
            result=dict(frozen=True,questions=15,identity_sha256=digest(identity),model_calls=0)
        else:
            from .backend import HFBackend
            result=run_final15(config,HFBackend(config),args.output)
    elif args.command=='report-final15':
        result=final_report(args.results)
    elif args.command=='bundle-final15':
        result=bundle_final15(args.results,args.output)
    else:
        result = dict(registered_questions=register_holdout(args.input, args.output), executed=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
