"""All-question answer/coverage metrics, and independently annotated semantics."""
from collections import Counter
import csv
from pathlib import Path
import random
from .common import ROOT, atomic_json, digest, file_digest, read_json, read_jsonl, write_jsonl
from .rag_runner import execution_summary, METHODS
from hotpotqa_operadic_rag.metrics import squad_em, squad_f1


def records(output):
    output=Path(output)
    return [read_json(p) for p in sorted((output/'trials').glob('*.json'))]


def references(output):
    lock=read_json(Path(output)/'RAG_LOCK.json')
    path=ROOT/('private/final15_labels.jsonl' if lock['role']=='heldout' else 'private/development_labels.jsonl')
    if file_digest(path)!=lock['identity']['reference_labels_sha256']:
        raise ValueError('Reference labels differ from the frozen run')
    return {r['source_question_id']:r for r in read_jsonl(path)}


def ratio(n,d):
    return n/d if d else None


def coverage(trial,reference):
    gold={tuple(f) for f in reference['supporting_facts']}
    found={(p['title'],sid) for p in trial['evidence_final'] for sid in p['sentence_ids']}
    return ratio(len(gold&found),len(gold))


def report_rag(output):
    output=Path(output)
    execution=execution_summary(output)
    refs=references(output)
    trials=records(output)
    metrics={}
    for method in METHODS:
        rows=[r for r in trials if r['method']==method]
        complete=len(rows)==execution['question_count']
        totals=[r['costs']['total_tokens'] for r in rows]
        charged=[r['costs']['charged_total_tokens'] for r in rows]
        times=[r['execution_seconds'] for r in rows]
        charged_times=[r.get('charged_execution_seconds_with_plan') for r in rows]
        cover=[coverage(r,refs[r['question_id']]) for r in rows]
        metrics[method]=dict(recorded_questions=len(rows),expected_questions=execution['question_count'],
            statuses=dict(Counter(r['status'] for r in rows)),
            answer_accuracy=ratio(sum(squad_em(r['answer'],refs[r['question_id']]['answer']) for r in rows),len(rows)) if complete else None,
            answer_f1=ratio(sum(squad_f1(r['answer'],refs[r['question_id']]['answer']) for r in rows),len(rows)) if complete else None,
            answer_accuracy_definition='Exact Match over ALL questions, including failures and abstentions; F1 reported separately.',
            supporting_fact_coverage=ratio(sum(c for c in cover if c is not None),sum(c is not None for c in cover)) if complete else None,
            llm_calls=sum(r['costs']['llm_calls'] for r in rows),
            retrieval_calls=sum(r['costs']['retrieval_calls'] for r in rows),
            actual_tokens=sum(totals) if all(t is not None for t in totals) else None,
            charged_tokens_with_shared_plan=sum(charged) if all(t is not None for t in charged) else None,
            execution_seconds=sum(times) if all(t is not None for t in times) else None,
            charged_execution_seconds_with_plan=sum(charged_times) if all(t is not None for t in charged_times) else None,
            time_scope='Online runtime excludes shared model/index setup. Historical development-plan generation time is not comparable; charged time is null for those arms.',
            uncited_answer_rate=ratio(sum(bool(r['answer']) and not r['citations'] for r in rows),sum(bool(r['answer']) for r in rows)),
            premature_stopping=None,citation_faithfulness=None,independent_semantic_review='pending')
    result=dict(execution=execution,metrics=metrics,
        caveats=['Retrieved gold-fact coverage is not semantic sufficiency.',
                 'Citation IDs and support-verifier model verdicts are not independent ground truth.',
                 'The three methods differ in more than graph visibility; use the retained one-step ablation for that narrower comparison.',
                 'No answer-success or novelty claim is implied by offline software tests.'])
    result['paired_answer_comparisons']=[]
    if execution['execution_complete']:
        by_method={m:{r['question_id']:squad_em(r['answer'],refs[r['question_id']]['answer']) for r in trials if r['method']==m} for m in METHODS}
        for first,second in [('dependent','independent')]:
            keys=sorted(by_method[first])
            deltas=[by_method[first][q]-by_method[second][q] for q in keys]
            rng=random.Random(42)
            boot=sorted(sum(rng.choice(deltas) for _ in deltas)/len(deltas) for _ in range(2000))
            result['paired_answer_comparisons'].append(dict(first=first,second=second,questions=len(deltas),
                em_difference=sum(deltas)/len(deltas),interval_95=[boot[49],boot[1949]] if len(deltas)>1 else None,
                method='Paired bootstrap over independent questions, 2000 draws; small-sample uncertainty remains.'))
    semantic=output/'semantic_evaluation.json'
    if semantic.exists():
        value=read_json(semantic)
        if value['trials_sha256']!=digest(trials):
            raise ValueError('Semantic scores no longer match saved trials')
        result['independent_evaluation']=value
        result['execution']['independent_semantic_evaluation_complete']=value['complete']
        for method,semantic_metrics in value['metrics'].items():
            result['metrics'][method].update(semantic_metrics)
            reviewed=semantic_metrics['reviewed_questions']
            result['metrics'][method]['independent_semantic_review']=(
                'complete' if reviewed==execution['question_count'] else 'partial' if reviewed else 'pending')
    atomic_json(output/'rag_report.json',result)
    fields=['method','recorded_questions','expected_questions','answer_accuracy','answer_f1',
            'supporting_fact_coverage','premature_stopping','citation_faithfulness','independent_semantic_review',
            'llm_calls','retrieval_calls','actual_tokens','charged_tokens_with_shared_plan','execution_seconds',
            'charged_execution_seconds_with_plan','uncited_answer_rate']
    with (output/'rag_metrics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        for method,values in result['metrics'].items():writer.writerow(dict(values,method=method))
    (output/'RAG_REPORT_FA.txt').write_text(
        'گزارش اجرای زوجی کنترل‌گر\n'
        +f"سؤال‌ها: {execution['question_count']}؛ رکوردها: {execution['recorded_trials']}/{execution['expected_trials']}\n"
        +f"فراخوانی واقعی مدل: {execution['actual_llm_calls']}؛ بازیابی: {execution['actual_retrieval_calls']}؛ توکن: {execution['actual_total_tokens']}\n"
        +'جزئیات هر روش در rag_report.json؛ شواهد، تصمیم‌ها و مصرف هر فراخوانی در trials و calls است.\n'
        +'دقت EM و F1 بر همهٔ سؤال‌ها محاسبه می‌شود؛ شکست‌ها حذف نشده‌اند.\n'
        +'کفایت معنایی، توقف زودهنگام و اعتبار ارجاع به داوری مستقل نیاز دارند؛ مقدار خالی صفر نیست.\n',encoding='utf-8')
    return result


def export_rag_review(output,destination):
    output,destination=Path(output),Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Use a new review directory')
    qs={q['question_id']:q for q in read_json(output/'runtime_questions.json')}
    refs=references(output)
    packets,mapping=[],{}
    for trial in records(output):
        key=digest([trial['question_id'],trial['method'],file_digest(output/'RAG_LOCK.json')])[:24]
        starts=[i for i,e in enumerate(trial['events']) if e['kind']=='round_started']
        latest=None
        if starts:
            current=trial['events'][starts[-1]+1:]
            latest=[]
            for event in current:
                if event['kind']=='node_assessed':latest.append({k:v for k,v in event.items() if k!='kind'})
                elif event['kind']=='node_blocked':latest.append(dict(id=event['node_id'],question=event['question'],
                    status='blocked',answer='',refs=[],missing_dependencies=event['missing_dependencies']))
        if latest is None:
            rounds=trial['details'].get('node_rounds',[])
            latest=rounds[-1]['nodes'] if rounds else []
        plan_path=output/'plans'/(trial['question_id']+'.json')
        plan=read_json(plan_path).get('plan') if plan_path.exists() else None
        if trial['method']!='standard' and plan:
            assessed={n['id'] for n in latest}
            latest=latest+[dict(id=n['id'],question=n['question'],status='not_evaluated',answer='',refs=[])
                           for n in plan['nodes'] if n['id'] not in assessed]
        packet=dict(review_id=key,question=qs[trial['question_id']]['question'],answer=trial['answer'],
            evidence=trial['evidence_final'],citations=trial['citations'],node_assessments=latest,
            reference=dict(answer=refs[trial['question_id']]['answer'],supporting_facts=refs[trial['question_id']]['supporting_facts']),
            review=dict(final=False,reviewer_id='',state_sufficient=None,binding_correct=None,
                        cited_claims=None,entailed_cited_claims=None,required_claims=None,entailed_required_claims=None,
                        subquestions=[dict(id=n['id'],support_assessment_correct=None,binding_correct=None) for n in latest],comment=''))
        packets.append(packet)
        mapping[key]=dict(question_id=trial['question_id'],method=trial['method'],trial_sha256=digest(trial),
                          content_sha256=digest({k:v for k,v in packet.items() if k!='review'}))
    packets.sort(key=lambda p:p['review_id'])
    write_jsonl(destination/'review_packets.jsonl',packets)
    atomic_json(destination/'private_mapping.json',mapping)
    return dict(packets=len(packets),note='Keep private_mapping from the reviewer; behavior may still reveal the method.')


def score_rag_review(output,packets_path,mapping_path):
    output=Path(output)
    trials=records(output)
    by_key={(r['question_id'],r['method']):r for r in trials}
    mapping=read_json(mapping_path)
    judged={m:[] for m in METHODS}
    seen=set()
    for packet in read_jsonl(packets_path):
        rid=packet['review_id']
        if rid in seen or rid not in mapping:raise ValueError('Duplicate or unknown review')
        seen.add(rid)
        item=mapping[rid]
        trial=by_key[(item['question_id'],item['method'])]
        if digest(trial)!=item['trial_sha256'] or digest({k:v for k,v in packet.items() if k!='review'})!=item['content_sha256']:
            raise ValueError('Review or trial content changed')
        review=packet['review']
        if review['final'] is not True:continue
        if not isinstance(review['reviewer_id'],str) or not review['reviewer_id'].strip():raise ValueError('Missing reviewer')
        if any(type(review[k]) is not bool for k in ['state_sufficient','binding_correct']):raise ValueError('Missing semantic judgments')
        for total,part in [('cited_claims','entailed_cited_claims'),('required_claims','entailed_required_claims')]:
            if any(type(review[k]) is not int or review[k]<0 for k in [total,part]) or review[part]>review[total]:
                raise ValueError('Invalid claim counts')
        expected=[n['id'] for n in packet['node_assessments']]
        if [n['id'] for n in review['subquestions']]!=expected or any(type(n[k]) is not bool for n in review['subquestions']
                for k in ['support_assessment_correct','binding_correct']):raise ValueError('Incomplete subquestion review')
        judged[trial['method']].append((trial,review))
    metrics={}
    for method,rows in judged.items():
        stops=[(t,r) for t,r in rows if t['status']=='answered']
        metrics[method]=dict(reviewed_questions=len(rows),premature_stop_denominator=len(stops),
            premature_stopping=ratio(sum(not r['state_sufficient'] for _,r in stops),len(stops)),
            premature_stop_all_reviewed=ratio(sum(not r['state_sufficient'] for _,r in stops),len(rows)),
            citation_faithfulness=ratio(sum(r['entailed_cited_claims'] for _,r in rows),sum(r['cited_claims'] for _,r in rows)),
            citation_completeness=ratio(sum(r['entailed_required_claims'] for _,r in rows),sum(r['required_claims'] for _,r in rows)),
            binding_correctness=ratio(sum(r['binding_correct'] for _,r in rows),len(rows)))
    execution=execution_summary(output)
    result=dict(trials_sha256=digest(trials),metrics=metrics,
                complete=execution['execution_complete'] and sum(len(r) for r in judged.values())==len(trials),
                scope='Independent supplied annotations; model support certificates are not evaluation labels.',
                stopping_definition='Returned successful answers on independently judged insufficient final evidence; budget abstentions separate.')
    atomic_json(output/'semantic_evaluation.json',result)
    return result
