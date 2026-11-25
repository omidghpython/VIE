from pathlib import Path
import sys,json,hashlib,shutil,tempfile,collections
src=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/workspace/VIE/experiments/evidence_planning_v0_3_3')
root=Path(sys.argv[3]) if len(sys.argv)>3 else Path(__file__).parent
r=Path(sys.argv[2]) if len(sys.argv)>2 else root/'rag_results'
sys.path.insert(0,str(src))
from planning_lab.common import read_json,digest,file_digest,verify_baseline
from planning_lab.rag_runner import load_questions,prepare_plan,_execute_trial
from planning_lab.rag_evaluation import report_rag
lock=read_json(r/'RAG_LOCK.json');ident=lock['identity'];qs=read_json(r/'runtime_questions.json');config=ident['config']
assert digest(ident)==lock['identity_sha256'];assert digest(qs)==ident['questions_sha256'];assert len(qs)==15
paths=sorted((src/'planning_lab').glob('*.py'))+[src/'run.py']
assert digest({str(p.relative_to(src)).replace('/','\\'):file_digest(p) for p in paths})==ident['source_sha256']
assert file_digest(src/'run_rag.py')==ident['entrypoint_sha256'];assert verify_baseline()['baseline_zip_sha256']==ident['baseline_sha256']
class Backend:
 def __init__(self,rows):self.rows=rows;self.i=0
 def count_tokens(self,messages):
  row=self.rows[self.i];assert messages==row['request']['messages'];self.i+=1;return row['prompt_tokens']
 def check_context(self,*args):pass
 def generate(self,*args):raise AssertionError('Fresh generation prohibited')
class Retriever:
 def __init__(self,passages):self.passages=passages
 def search(self,*args,**kwargs):raise AssertionError('Fresh search prohibited')
def rows(path):
 result=[read_json(p) for p in sorted(path.glob('*.json'))]
 for row in result:assert digest(row['request'])==row['request_sha256'];assert row['status']=='completed'
 return result
verified=[];plans=[]
for q in qs:
 qid=q['question_id'];savedplan=read_json(r/'plans'/(qid+'.json'));pc=r/'plan_calls'/qid;pr=rows(pc/'model_calls')
 with tempfile.TemporaryDirectory() as td:
  temp=Path(td);shutil.copytree(pc,temp/'plan_calls'/qid);backend=Backend(pr)
  actual=prepare_plan(q,config,backend,temp)
  for k,v in savedplan.items():
   if k!='elapsed_seconds':assert actual[k]==v,(qid,k)
  assert backend.i==len(pr)
 plans.append(dict(question_id=qid,model_calls=len(pr),status=savedplan['status'],tokens=savedplan['actual_new_usage']['total_tokens']))
 for method in ['standard','max4','operadic']:
  saved=read_json(r/'trials'/f'{qid}--{method}.json');calls=r/'calls'/qid/method;mr=rows(calls/'model_calls');rr=rows(calls/'retrieval_calls')
  for row in rr:
   for hit in row['hits']:
    corpus=q['passages'][hit['index']];assert all(hit[k]==v for k,v in corpus.items())
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'calls'
   if calls.exists():shutil.copytree(calls,out)
   backend=Backend(mr);result=_execute_trial(q,method,savedplan,config,backend,Retriever(q['passages']),out)
   for k,v in result.items():
    if k!='execution_seconds':assert saved[k]==v,(qid,method,k)
   assert backend.i==len(mr)
  verified.append(dict(question_id=qid,method=method,status=saved['status'],error=saved.get('error'),model_calls=len(mr),retrieval_calls=len(rr),tokens=saved['costs']['total_tokens']))
summary=read_json(r/'execution_summary.json');assert sum(x['model_calls'] for x in verified+plans)==summary['actual_llm_calls'];assert sum(x['tokens'] for x in verified+plans)==summary['actual_total_tokens'];assert sum(x['retrieval_calls'] for x in verified)==summary['actual_retrieval_calls']
audit=dict(source_matches_v034_windows=True,questions_match_recorded_lock=True,official_selection_independently_reproduced=False,reference_labels_missing_from_export=True,exact_plan_replays=len(plans),exact_trial_replays=len(verified),report_regenerated_exactly=False,model_call_journals_verified=summary['actual_llm_calls'],retrieval_call_journals_verified=summary['actual_retrieval_calls'],fresh_model_calls=0,fresh_search_calls=0,execution=summary,plans=plans,trials=verified)
(root/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print('Exact plans/trials replay verified; no fresh inference. Reference metrics cannot be regenerated without missing labels.')
