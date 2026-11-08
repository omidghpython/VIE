"""Usage: python preflight.py SOURCE_DIR BASELINE_RESULT_DIR OUTPUT_JSON. No inference."""
from pathlib import Path
import json, sys, hashlib, collections, copy
sys.dont_write_bytecode=True
source, baseline, output=map(Path,sys.argv[1:4]);sys.path.insert(0,str(source))
import decomposition_pilot as pilot
from hotpotqa_operadic_rag import decomposition as d
from hotpotqa_operadic_rag.contracts import parse_json_object
from hotpotqa_operadic_rag.relation_repair import diagnose, REPAIR_SYSTEM

read=lambda p:json.loads(p.read_text(encoding='utf-8'))
samples,baselines=pilot.load_cohort(source/'evaluation/samples.json')
assert samples==read(baseline/'trees.csv.state/samples.json')
settings=read(baseline/'trees.csv.state/manifest.json')['settings']
assert hashlib.sha256(d.PLAN_SYSTEM.encode()).hexdigest()==settings['plan_prompt_sha256']
assert hashlib.sha256(d.REVIEW_SYSTEM.encode()).hexdigest()==settings['review_prompt_sha256']

class Replay:
    plan_tokens=3072
    last_raw_output=None
    def __init__(self,raws):self.raws,self.messages=list(raws),[]
    def generate(self,messages,**kwargs):
        self.messages.append(copy.deepcopy(messages));self.last_raw_output=self.raws.pop(0);return self.last_raw_output
    def ask_json(self,prompt):self.last_raw_output=self.raws.pop(0);return parse_json_object(self.last_raw_output)

def make_proposal(question,plan):
    # Offline synthetic fixture ONLY; this function is not part of the runner or any model prompt.
    c=diagnose(question,plan);s=c['source'];candidate=copy.deepcopy(plan)
    root=next(n for n in candidate['nodes'] if n['id']==candidate['final'])
    if c['kind']=='founding_location':
        for entity,nid in c['bindings'].items():
            n=next(n for n in candidate['nodes'] if n['id']==nid)
            n.update(question='Where was '+entity+' founded?',answer_type='place')
        a,b=s['entities'];qa,qb=[c['bindings'][e] for e in (a,b)]
        root.update(question='Which '+s['category']+' was founded in '+s['place']+': '+a+' ({{'+qa+'}}) or '+b+' ({{'+qb+'}})?',
                    answer_type='other',dependencies={qa:'place',qb:'place'})
    else:
        nid=c['bindings']['river'];leaf=next(n for n in candidate['nodes'] if n['id']==nid)
        leaf.update(question='Which river is '+s['inverse']+' of the '+s['entity']+'?',answer_type='place')
        root.update(question='How long is {{'+nid+'}} in '+s['unit']+'?',answer_type='number',dependencies={nid:'place'})
    return candidate

attempts=reviews=0;triggered=[];rows=[];prompts=[];scripted=[]
for order,sample in enumerate(samples,1):
    rec=read(baseline/'trees.csv.state/questions'/(sample['question_id']+'.json'))
    st=rec['phases']['structure'];trace=st['result']['decomposition_trace']
    raw=[e['raw_output'] for e in trace];model=Replay(raw)
    try:r=pilot.generate_result(model,sample['question']);status='valid';error=''
    except d.DecompositionError as exc:r=exc.details;status='invalid';error=str(exc)
    assert (status,error,r)==(st['status'],st['error'],st['result'])
    assert not model.raws
    assert model.messages[0][1]['content']==sample['question']
    attempts+=len(trace)
    rev=rec['phases'].get('review')
    if rev:
        fake=Replay([rev['result']['raw_output']] if rev['result']['raw_output'] is not None else [])
        assert pilot.review_result(fake,sample['question'],r['plan'])==rev['result']
        assert not fake.raws
        reviews+=1
    diagnostic=diagnose(sample['question'],r.get('plan'))
    if diagnostic['status']=='mismatch':
        triggered.append(order)
        assert len(trace)==1
        proposal=make_proposal(sample['question'],r['plan'])
        fake=Replay(raw+[json.dumps(proposal)])
        repaired=pilot.generate_result(fake,sample['question'],relation_repair=True)
        assert repaired['relation_repair']['status']=='accepted' and not fake.raws
        assert len(fake.messages)==2
        prompts.append(dict(order=order,messages=fake.messages[1]))
        scripted.append(dict(order=order,proposal=proposal,meta=repaired['relation_repair']))
        # Actual old output used as failed candidate: known defect must remain visible.
        fail=pilot.generate_result(Replay(raw+raw),sample['question'],relation_repair=True)
        assert fail['plan']==r['plan'] and fail['relation_repair']['status']=='rejected'
    else:
        fake=Replay(raw)
        try:
            unchanged=pilot.generate_result(fake,sample['question'],relation_repair=True)
            assert unchanged['plan']==r.get('plan') and not unchanged['relation_repair']['attempted']
        except d.DecompositionError as exc:
            assert status=='invalid' and exc.details==st['result']
        assert not fake.raws
    rows.append(dict(order=order,question_id=sample['question_id'],question=sample['question'],diagnostic=diagnostic,
                     initial_prompt_sha256=hashlib.sha256(d.plan_instructions(sample['question']).encode()).hexdigest()))
assert triggered==[13,14]
result=dict(experiment='max4_direction_location_repair_v1',baseline='v3.2.4-max4',
            code_sha256=pilot.code_digest(),plan_prompt_sha256=settings['plan_prompt_sha256'],review_prompt_sha256=settings['review_prompt_sha256'],
            repair_prompt_sha256=hashlib.sha256(REPAIR_SYSTEM.encode()).hexdigest(),
            baseline_structure_attempts_replayed=attempts,baseline_review_decisions_replayed=reviews,
            all_baseline_control_results_exact=True,trigger_orders=triggered,untouched_other_questions=38,
            model_calls=0,synthetic_proposals_not_live_results=scripted,repair_prompts=prompts,questions=rows,
            live_results='pending',limitation='Synthetic accepted/rejected fixtures and saved-output replay are not Qwen repair success or semantic accuracy.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('code_sha256','baseline_structure_attempts_replayed','baseline_review_decisions_replayed','trigger_orders','untouched_other_questions','model_calls')},indent=2))
