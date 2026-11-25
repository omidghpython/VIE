from pathlib import Path
import csv,tempfile
from checks.synthetic_fixture import ScriptBackend,fixture,plan_record,CONFIG
from planning_lab.rag_retrieval import BM25Retriever,RetrieverFactory
from planning_lab.rag_runner import execute_trial,run_rag,load_questions
from planning_lab.paired_review import export,score,ARMS
from planning_lab.rag_evaluation import report_rag
from planning_lab.common import read_json

with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    q=fixture()
    for mode in ('normal','reject_support'):
        for arm in ARMS:
            t=execute_trial(q,arm,plan_record(q),CONFIG,ScriptBackend(mode),
                BM25Retriever(q['passages']),base/mode/arm)
            assert t['status']==('answered' if mode=='normal' else 'budget_exhausted'),t
            inputs=[e for e in t['events'] if e['kind']=='node_inputs']
            assert any(e['consumed_dependencies'] for e in inputs)==(arm=='dependent' and mode=='normal')
            assert any(e['kind']=='node_blocked' for e in t['events'])==(arm=='dependent' and mode=='reject_support')
            assert t['costs']['retrieval_calls']<=2
    output=base/'software-check'
    backend=ScriptBackend(); factory=RetrieverFactory(CONFIG);questions=load_questions('development')
    summary=run_rag(questions,CONFIG,backend,factory,output,progress=lambda _:None)
    assert summary['recorded_trials']==summary['expected_trials']==80
    report=report_rag(output)
    assert all(m['statuses']['invalid_plan']==3 for m in report['metrics'].values())
    count=len(backend.messages)
    run_rag(questions,CONFIG,backend,factory,output,progress=lambda _:None)
    assert len(backend.messages)==count
    export(output)
    with (output/'decision_template.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    for row in rows:
        for k in row:
            if row[k]=='':row[k]='unknown'
        row['reason']='Software fixture'
    with (base/'ratings.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    score(output,base/'ratings.csv')
    assert read_json(output/'paired_decision_scores.json')['counts']['unrated']==40
    print('PASS: dependency use, blocking, recovery, common initial evidence, 80 records, metrics and review. Synthetic model only.')
