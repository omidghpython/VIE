"""Pair outcomes by question and keep semantic ratings separate from model claims."""
import csv
from pathlib import Path
from .common import atomic_json, digest, read_json, write_jsonl
from .rag_evaluation import records

ARMS = ('dependent', 'independent')
NODE = ('evidence_sufficient', 'entity_correct', 'property_correct', 'value_supported',
        'wrong_value_transferred', 'supported_answer_rejected')
ACTION = ('action_appropriate', 'unnecessary_retrieval', 'premature_stop')


def export(output):
    output = Path(output)
    questions = {q['question_id']: q for q in read_json(output/'runtime_questions.json')}
    packets, template, mapping, initial = [], [], {}, {}
    for trial in records(output):
        qid, arm = trial['question_id'], trial['method']
        q = questions[qid]
        seen, inputs, assessments = [], {}, []
        for index, event in enumerate(trial['events']):
            kind = event['kind']
            if kind == 'retrieval_executed':
                if not seen:
                    initial.setdefault(qid, {})[arm] = event['new_indices']
                seen.extend(event['new_indices'])
            if kind == 'round_started':
                assessments = []
            if kind == 'node_inputs':
                inputs[event['node_id']] = event
            if kind not in ('controller_decision', 'node_assessed', 'node_blocked'):
                continue
            task = 'action' if kind == 'controller_decision' else 'node'
            rid = digest([qid, arm, index])[:20]
            candidate = event.get('candidate') or {}
            mapping[rid] = dict(question_id=qid, arm=arm, task=task)
            packets.append(dict(review_id=rid, question=q['question'], task=task,
                evidence=[q['passages'][i] for i in seen], event=event,
                inputs=inputs.get(event.get('id')) if kind=='node_assessed' else None,
                system_answer_present=bool(candidate.get('answer')) if task=='node' else None,
                runtime_accepted=event.get('status')=='supported' if task=='node' else None))
            if task=='node':
                assessments.append(event)
            else:
                packets[-1]['current_node_states']=list(assessments)
            template.append(dict(review_id=rid, task=task, **dict.fromkeys(NODE+ACTION+('citations_faithful',),''), reason=''))
        rid=digest([qid,arm,'final'])[:20]
        mapping[rid]=dict(question_id=qid,arm=arm,task='final')
        packets.append(dict(review_id=rid,task='final',question=q['question'],answer=trial['answer'],
                            citations=trial['citations'],evidence=trial['evidence_final']))
        template.append(dict(review_id=rid,task='final',**dict.fromkeys(NODE+ACTION+('citations_faithful',),''),reason=''))
    for qid, pair in initial.items():
        if len(pair)==2 and pair[ARMS[0]]!=pair[ARMS[1]]:
            raise ValueError('First retrieval mismatch: '+qid)
    write_jsonl(output/'decision_packets.jsonl',sorted(packets,key=lambda p:p['review_id']))
    atomic_json(output/'decision_mapping.json',mapping)
    if template:
        with (output/'decision_template.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(template[0]));w.writeheader();w.writerows(sorted(template,key=lambda r:r['review_id']))
    return mapping


def score(output, csv_path):
    mapping=export(output)
    trials={(t['question_id'],t['method']):t for t in records(output)}
    values={}
    with Path(csv_path).open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            rid=row['review_id']
            if rid not in mapping or rid in values or row['task']!=mapping[rid]['task']:
                raise ValueError('Unexpected, duplicate or mismatched review ID')
            fields={'node':NODE,'action':ACTION,'final':('citations_faithful',)}[row['task']]
            if any(row[k] not in ('yes','no','na','unknown') for k in fields) or not row['reason'].strip():
                raise ValueError('Rate applicable fields and provide a reason: '+rid)
            values[rid]=row
    if set(values)!=set(mapping):raise ValueError('Incomplete review')
    paired=[]
    for q in read_json(Path(output)/'runtime_questions.json'):
        qid=q['question_id'];pair={}
        for arm in ARMS:
            subset=[values[i] for i,k in mapping.items() if (k['question_id'],k['arm'])==(qid,arm)]
            actions=[r for r in subset if r['task']=='action']
            t=trials.get((qid,arm),{})
            pair[arm]={'status':t.get('status','pending'),'unanswered':not bool(t.get('answer')),
                'inappropriate_actions':sum(r['action_appropriate']=='no' for r in actions)
                    if actions and all(r['action_appropriate'] in ('yes','no') for r in actions) else None}
            pair[arm]['citations_faithful']=next((r['citations_faithful'] for r in subset if r['task']=='final'),None)
            for k in ('wrong_value_transferred','supported_answer_rejected','unnecessary_retrieval','premature_stop'):
                applicable=[r[k] for r in subset if r['task']==('action' if k in ACTION else 'node')]
                pair[arm][k]=sum(v=='yes' for v in applicable) if applicable and 'unknown' not in applicable else None
        a,b=(pair[arm]['inappropriate_actions'] for arm in ARMS)
        outcome='unrated' if a is None or b is None else 'better' if a<b else 'worse' if a>b else 'tie'
        paired.append(dict(question_id=qid,arms=pair,dependent_outcome=outcome))
    atomic_json(Path(output)/'paired_decision_scores.json',dict(questions=paired,
        counts={v:sum(r['dependent_outcome']==v for r in paired) for v in ('better','worse','tie','unrated')}))
