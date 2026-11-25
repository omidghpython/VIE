from pathlib import Path
import sys,json,tempfile,shutil,csv
root=Path(__file__).parent;src=root/'source_with_metadata';r=root/'rag_results';sys.path.insert(0,str(src))
from planning_lab.common import read_json,read_jsonl,digest,file_digest,write_jsonl
from tools.prepare_official_final15 import materialize
from planning_lab.rag_runner import load_questions
from planning_lab.rag_evaluation import report_rag
from hotpotqa_operadic_rag.metrics import squad_em,squad_f1
m=read_json(src/'data/final15_manifest.json');original=read_json(src/'private/final15_original_records.json');reg=read_json(src/'data/split_registry.json');exp=read_json(src/'provenance/known_exposure_registry.json');labels=read_jsonl(src/'private/final15_labels.jsonl');lock=read_json(r/'RAG_LOCK.json')
assert file_digest(src/'private/final15_labels.jsonl')==lock['identity']['reference_labels_sha256']
assert digest(original)==m['originals_sha256'];assert digest(labels)==m['labels_sha256'];assert digest(exp)==m['known_exposure_sha256'];assert digest(reg['heldout'])==m['registry_sha256']
with tempfile.TemporaryDirectory() as td:
 temp=Path(td);new=materialize(original,m['eligible_pool_records'],exp,reg,m['obtained_via'],temp);assert new==m
 for p in ['private/final15_labels.jsonl','private/final15_original_records.json','data/split_registry.json']:
  if p.endswith('.jsonl'):assert read_jsonl(src/p)==read_jsonl(temp/p)
  else:assert read_json(src/p)==read_json(temp/p)
 shutil.copy(temp/'data/final15_questions.jsonl',src/'data/final15_questions.jsonl')
assert load_questions('heldout')==read_json(r/'runtime_questions.json')
with tempfile.TemporaryDirectory() as td:
 temp=Path(td)/'results';shutil.copytree(r,temp);assert report_rag(temp)==read_json(r/'rag_report.json')
ref={x['source_question_id']:x for x in labels};out=[]
for i,q in enumerate(read_json(r/'runtime_questions.json'),1):
 row={'number':i,'question':q['question'],'reference':ref[q['question_id']]['answer']}
 for method in ['standard','max4','operadic']:
  t=read_json(r/'trials'/f"{q['question_id']}--{method}.json");row[method+'_answer']=t['answer'];row[method+'_EM']=squad_em(t['answer'],row['reference'])
 out.append(row)
(root/'verified_scores.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
with (root/'verified_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]),lineterminator='\n');w.writeheader();w.writerows(out)
for x in out:print(x['number'],repr(x['reference']),repr(x['max4_answer']),x['max4_EM'])
print('Metadata hashes, selected record construction, runtime questions and entire report verified. Full 7405-record source not supplied: global seed sampling and original40 reproduction remain recorded preparer attestations, not independent full-source replay.')
