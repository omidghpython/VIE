import argparse
import zipfile
from pathlib import Path
from planning_lab.common import ROOT,read_json
from planning_lab.rag_runner import load_questions,run_rag,validate_rag_config
from planning_lab.rag_evaluation import report_rag
from planning_lab.paired_review import export,score
from planning_lab.console import ConsoleProgress

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['verify','run','report','score','bundle'])
    parser.add_argument('--ratings',type=Path)
    args=parser.parse_args()
    config=read_json(ROOT/'configs/rag_development.json')
    validate_rag_config(config)
    qs=load_questions('development')
    if len(qs)!=40:raise ValueError('Expected the frozen development40')
    out=ROOT/'results/oc_ablation_01_dev40'
    if args.action=='verify':
        print('40 registered development questions; 80 paired trial records expected.')
        return
    if args.action=='run':
        from planning_lab.backend import HFBackend
        from planning_lab.rag_retrieval import RetrieverFactory
        console=ConsoleProgress(out)
        try:
            print('Loading Qwen and the shared retrieval model...',flush=True)
            run_rag(qs,config,HFBackend(config),RetrieverFactory(config),out,observer=console)
        finally:console.close()
    if args.action=='score':
        if not args.ratings:parser.error('Provide --ratings completed.csv')
        score(out,args.ratings)
        return
    if (out/'.run.lock').exists():raise ValueError('Run is active')
    report_rag(out)
    export(out)
    if args.action=='bundle':
        with zipfile.ZipFile(ROOT/'OC_ABLATION_01_DEV40_results.zip','x',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(out.rglob('*')):
                if f.is_file():z.write(f,'results/'+f.relative_to(out).as_posix())
    print(out)

if __name__=='__main__':main()
