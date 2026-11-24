"""Synthetic UI demonstration; never uses the real heldout15 records or model."""
from pathlib import Path
import sys, tempfile, io, json
from unittest.mock import patch
src=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).parent/'hotpotqa_evidence_planning_v3'
sys.path[:0]=[str(src),str(src/'tests')]
from planning_lab.console import ConsoleProgress
from planning_lab.common import atomic_json,digest
from planning_lab import rag_runner as runner
from test_rag import fixture,ScriptBackend,CONFIG
from planning_lab.rag_retrieval import RetrieverFactory
qs=[]
for i in range(15):
 q=fixture('synthetic-validation-'+str(i))
 for k in ['frozen_plan','structure_valid','plan_debit']:q.pop(k)
 q['role']='heldout';q['question']+=' [Synthetic example '+str(i)+']';qs.append(q)
backend=ScriptBackend();factory=RetrieverFactory(CONFIG);config=dict(CONFIG,role='heldout')
first=sorted(qs,key=lambda q:digest([config['seed'],q['question_id']]))[0]['question']
original=runner.METHODS['operadic']
def example_failure(question,*args):
 backend.mode='reject_support' if question==first else 'normal'
 try:return original(question,*args)
 finally:backend.mode='normal'
stream=io.StringIO()
stream.write('SYNTHETIC CONSOLE PREVIEW: 15 invented examples, scripted model replies, CPU BM25.\nNOT the real validation15, NOT Qwen/GPU inference or measured model accuracy.\n\n')
console=ConsoleProgress(stream=stream)
with tempfile.TemporaryDirectory() as td:
 root=Path(td);(root/'run_rag.py').write_text('# synthetic entrypoint')
 atomic_json(root/'private/final15_labels.jsonl',{})
 console('startup',version='0.3.3 SYNTHETIC PREVIEW',role='heldout (synthetic)',questions=15,config=config,cap=None,output=str(root/'results'))
 console('setup',message='Synthetic backend ready; real models are NOT loaded in this preview')
 with patch.object(runner,'ROOT',root),patch.object(runner,'load_questions',return_value=qs),patch.dict(runner.METHODS,operadic=example_failure):
  summary=runner.run_rag(qs,config,backend,factory,root/'results',progress=lambda _:None,observer=console)
 assert summary['recorded_trials']==45 and summary['execution_complete']
 rows=[json.loads(p.read_text()) for p in (root/'results/trials').glob('*.json')]
 assert sum(t['status']=='budget_exhausted' for t in rows)==1
 from collections import Counter
 counts=dict(Counter(t['status'] for t in rows))
 console.close()
 log=stream.getvalue().replace(td,'<temporary-synthetic-workspace>')
(Path(__file__).parent/'console_preview.txt').write_text(log,encoding='utf-8')
(Path(__file__).parent/'preview_verification.json').write_text(json.dumps(dict(synthetic=True,questions=15,records=45,statuses=counts,real_model_calls=0,real_heldout_questions_used=0,real_gpu_used=False,model='ScriptBackend',retrieval='real CPU BM25 over invented passages',full_log='console_preview.txt'),indent=2)+'\n')
assert not (src/'data/final15_usage.json').exists()
print('Synthetic preview:',len(rows),'records;',counts,'; real validation15 untouched.')
