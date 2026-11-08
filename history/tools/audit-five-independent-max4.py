# Usage: python audit-five-independent-max4.py EXPERIMENT_DIR BASELINE_RESULT_DIR BASELINE_SOURCE_DIR REPORT_OUTPUT_DIR
from pathlib import Path
import sys,json,hashlib,zipfile,copy,tempfile,collections

report_dir=Path(sys.argv[4]);report_dir.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True
dst=Path(sys.argv[1]);sys.path.insert(0,str(dst))
import decomposition_pilot as pilot
from hotpotqa_operadic_rag import decomposition as d
from hotpotqa_operadic_rag.contracts import parse_json_object
from hotpotqa_operadic_rag.checkpoint import RunStore
name=dst.name.removeprefix('hotpotqa_')
base=Path(sys.argv[2])  # extracted original max4 result folder containing summary.json
baseline_source=Path(sys.argv[3])  # freshly extracted accepted max4 source folder
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sn={};exec(compile((baseline_source/'hotpotqa_operadic_rag/semantic_checks.py').read_text(),'baseline_semantic','exec'),sn)
dn={'__package__':'hotpotqa_operadic_rag'};exec(compile((baseline_source/'hotpotqa_operadic_rag/decomposition.py').read_text(),'baseline_decomposition','exec'),dn)
dn['answer_target']=sn['answer_target']
cohort,baselines=pilot.load_cohort(dst/'evaluation/samples.json')
class Replay:
 plan_tokens=3072
 last_raw_output=None
 def __init__(self,raw):self.raw=list(raw);self.messages=[]
 def generate(self,messages,**kwargs):self.messages.append(copy.deepcopy(messages));self.last_raw_output=self.raw.pop(0);return self.last_raw_output
 def ask_json(self,prompt):self.last_raw_output=self.raw.pop(0);return parse_json_object(self.last_raw_output)

attempts=reviews=0; trace_diff=[]; hint_diff=[]; rows=[]; advisory=[]; mode_diffs=[]
for order,s in enumerate(cohort,1):
 rec=read(base/'trees.csv.state/questions'/(s['question_id']+'.json'));st=rec['phases']['structure'];oldtrace=st['result']['decomposition_trace']
 model=Replay([e['raw_output'] for e in oldtrace])
 try:result=pilot.generate_result(model,s['question']);status='valid'
 except d.DecompositionError as e:result=e.details;status='invalid'
 assert status==st['status'] and result.get('plan')==st['result'].get('plan'),(name,order,'decisions changed')
 assert not model.raw;attempts+=len(oldtrace)
 if result!=st['result']:trace_diff.append(order)
 before=dn['plan_instructions'](s['question']);after=d.plan_instructions(s['question'])
 if before!=after:hint_diff.append(dict(order=order,before=before[len(d.PLAN_SYSTEM):],after=after[len(d.PLAN_SYSTEM):]))
 rev=rec['phases'].get('review')
 if rev:
  fake=Replay([rev['result']['raw_output']] if rev['result']['raw_output'] is not None else [])
  current=pilot.review_result(fake,s['question'],result['plan'])
  assert current['verdict']==rev['result']['verdict'],(order,'review verdict changed')
  assert not fake.raw;reviews+=1
  if name[5:7] in ('02','04','05'):assert current==rev['result'],(order,'full review changed')
 if name[5:7] in ('02','04','05'):
  from hotpotqa_operadic_rag.experiment_diagnostics import analyze
  advisory.append(dict(order=order,question=s['question'],diagnostic=analyze(s['question'],result.get('plan'))))
 if name[5:7]=='03' and status=='valid':
  beforecheck=d.root_answer_check(s['question'],result['plan'])
  if beforecheck['status']=='mismatch':mode_diffs.append(dict(order=order,patch_eligible=len(oldtrace)<2,root_contract=beforecheck))
 rows.append(dict(order=order,status=status,plan_identical=True))

if name[5:7] in ('02','04','05'):
 assert not trace_diff and not hint_diff
 # Use a disposable copy of saved records solely to rebuild advisory reports; preserve original manifest identity.
 import shutil
 with tempfile.TemporaryDirectory() as tmp:
  output=Path(tmp)/'baseline_replay';shutil.copytree(base/'trees.csv.state',output/'trees.csv.state')
  settings=read(base/'trees.csv.state/manifest.json')['settings']
  store=RunStore(output/'trees.csv',settings,lambda:cohort)
  summary=pilot.export_reports(store,baselines)
  assert summary==read(base/'summary.json')
  comparison=read(output/'max4_comparison.json')
  assert comparison['metrics_comparable'] and all(q['plan_identical_to_max4'] for q in comparison['questions'])
  with zipfile.ZipFile(output.with_name(output.name+'_results.zip')) as z:
   assert z.testzip() is None and len(z.namelist())==49
  (report_dir/'saved_baseline_diagnostics.json').write_text(json.dumps(read(output/'diagnostics.json'),ensure_ascii=False,indent=2)+'\n')
  (report_dir/'saved_baseline_diagnostics.md').write_text((output/'diagnostics.md').read_text())
changed=[];added=[];unchanged=0
for p in sorted(dst.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
 rel=p.relative_to(dst).as_posix();orig=baseline_source/rel
 if not orig.exists():added.append(rel)
 elif orig.read_bytes()!=p.read_bytes():changed.append(rel)
 else:unchanged+=1
report=dict(experiment=name,baseline_zip_sha256='ad77a0d34992910d089f13fa30efee27040132bc3a93e6c8d868a10ef5a0a62b',
 source_code_sha256=pilot.code_digest(),samples_sha256=sha(dst/'evaluation/samples.json'),
 plan_prompt_sha256=hashlib.sha256(d.PLAN_SYSTEM.encode()).hexdigest(),review_prompt_sha256=hashlib.sha256(d.REVIEW_SYSTEM.encode()).hexdigest(),
 model=pilot.MODEL_NAME,model_revision=pilot.MODEL_REVISION,max_nodes=pilot.MAX_PLAN_NODES,plan_attempts=pilot.PLAN_ATTEMPTS,
 static_prompts_unchanged=d.PLAN_SYSTEM==dn['PLAN_SYSTEM'] and d.REVIEW_SYSTEM==dn['REVIEW_SYSTEM'],
 saved_output_replay=dict(questions=40,structure_attempts=attempts,review_decisions=reviews,all_structural_decisions_and_plans_unchanged=True,
                          trace_metadata_or_error_changed_orders=trace_diff,first_prompt_changed=hint_diff),
 target_patch_eligibility_on_saved_baseline=mode_diffs,advisory_on_saved_baseline=advisory,
 changed_files_before_packaging=changed,added_files_before_packaging=added,unchanged_files=unchanged,
 live_model_calls=0,live_results='pending',semantic_accuracy_measured=False,
 note='Replay uses original recorded outputs, NOT generated experimental outputs. Diagnostic-only changes do not improve those outputs.')
assert report['static_prompts_unchanged']
(report_dir/'PREFLIGHT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(experiment=name,attempts=attempts,reviews=reviews,hint_changed=[r['order'] for r in hint_diff],
                     trace_changed=trace_diff,patch_eligible=[r['order'] for r in mode_diffs if r['patch_eligible']],
                     advisory_counts=dict(collections.Counter(r['diagnostic']['status'] for r in advisory)),
                     suspicious=[r['order'] for r in advisory if r['diagnostic']['status']=='suspicious']),ensure_ascii=False))
