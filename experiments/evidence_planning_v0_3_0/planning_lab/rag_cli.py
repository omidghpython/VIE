"""CLI for live three-method RAG, separately from the retained one-step study."""
import argparse
import json
from pathlib import Path
import zipfile
from .common import ROOT, file_digest, read_json, verify_baseline
from .rag_runner import load_questions, freeze_rag, run_rag, validate_rag_config
from .rag_evaluation import report_rag, export_rag_review, score_rag_review


def main(argv=None):
    parser=argparse.ArgumentParser(description='Three-method RAG with actual retrieval and active Operadic stopping gate')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('verify')
    for name in ['freeze','run']:
        p=commands.add_parser(name)
        p.add_argument('--config',type=Path,default=ROOT/'configs/rag_development.json')
        p.add_argument('--output',type=Path,required=True)
        p.add_argument('--development-limit',type=int)
        if name=='run':p.add_argument('--max-new-questions',type=int)
    for name in ['report','export-review','score','bundle']:
        p=commands.add_parser(name)
        p.add_argument('--results',type=Path,required=True)
        if name in {'export-review','bundle'}:p.add_argument('--output',type=Path,required=True)
        if name=='score':
            p.add_argument('--reviews',type=Path,required=True)
            p.add_argument('--mapping',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command=='verify':
        base=verify_baseline()
        development=load_questions('development')
        final=load_questions('heldout')
        for name in ['rag_development','rag_final15']:validate_rag_config(read_json(ROOT/'configs'/f'{name}.json'))
        package=ROOT/'PACKAGE_MANIFEST.json'
        if package.exists():
            for name,expected in read_json(package)['files'].items():
                if file_digest(ROOT/name)!=expected:raise ValueError('Package file changed: '+name)
        result=dict(version='0.3.0',unchanged_baseline_files=len(base['unchanged_files']),
            development_questions=len(development),final_questions=len(final),methods=['standard','max4','operadic'],
            live_model_calls=0,live_retrieval_calls=0,final15_usage_marker_present=(ROOT/'data/final15_usage.json').exists(),
            note='Static preflight only; live inference and semantic improvement are not claimed.')
    elif args.command in {'freeze','run'}:
        config=read_json(args.config)
        questions=load_questions(config['role'])
        if args.development_limit is not None:
            if config['role']!='development' or args.development_limit<1:raise ValueError('Only development permits a positive subset limit')
            questions=questions[:args.development_limit]
        identity=freeze_rag(config,questions,args.output)
        if args.command=='freeze':result=dict(frozen=True,questions=len(questions),identity=identity)
        else:
            from .backend import HFBackend
            from .rag_retrieval import RetrieverFactory
            factory=RetrieverFactory(config)
            backend=HFBackend(config)
            result=run_rag(questions,config,backend,factory,args.output,max_new_questions=args.max_new_questions)
            report_rag(args.output)
    elif args.command=='report':result=report_rag(args.results)
    elif args.command=='export-review':result=export_rag_review(args.results,args.output)
    elif args.command=='score':
        result=score_rag_review(args.results,args.reviews,args.mapping)
        report_rag(args.results)
    else:
        report_rag(args.results)
        if args.output.exists():raise ValueError('Result archive already exists')
        if (args.results/'.run.lock').exists():raise ValueError('Do not bundle an active run')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(args.results.rglob('*')):
                if path.is_file() and path.resolve()!=args.output.resolve():
                    archive.write(path,'rag_results/'+path.relative_to(args.results).as_posix())
        result=dict(output=str(args.output),sha256=file_digest(args.output))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
