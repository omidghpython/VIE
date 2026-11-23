"""Independent manual review, with explicit missingness and denominators."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import random
from .common import ROOT, atomic_json, digest, read_json, read_jsonl, write_jsonl
from .prompts import task_view
from .runner import summarize_run
from hotpotqa_operadic_rag.metrics import squad_em, squad_f1


def load_trials(output):
    return [read_json(p) for p in sorted((Path(output) / 'trials').glob('*.json'))]


def export_review(output, destination, labels_path):
    output, destination = Path(output), Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Review destination must be new/empty; do not overwrite human annotations.')
    destination.mkdir(parents=True, exist_ok=True)
    labels = {r['case_id']: r for r in read_jsonl(labels_path)}
    cases = {c['case_id']: c for c in read_json(output / 'runtime_cases.json')}
    manifest = read_json(output / 'manifest.json')
    packets, mapping = [], {}
    for trial in load_trials(output):
        if trial['status'] != 'completed':
            continue
        case = cases[trial['case_id']]
        label = labels.get(trial['case_id'])
        if label is None:
            raise ValueError('Evaluation label record missing; cannot silently substitute a reference')
        if label['source_question_id'] != case['source_question_id']:
            raise ValueError('Reference question mismatch')
        review_id = digest([manifest['identity'], trial['trial_id'], 'blind_review'])[:32]
        mapping[review_id] = dict(trial_id=trial['trial_id'], case_id=trial['case_id'], arm=trial['arm'],
                                 trial_sha256=digest(trial))
        tasks, _ = task_view(case)
        packets.append(dict(review_id=review_id, question=case['question'], tasks=tasks,
                            evidence=case['evidence'], output=trial['parsed'],
                            reference=dict(answer=label['answer'], supporting_facts=label['supporting_facts']),
                            review=dict(final=False, reviewer_id='', state_sufficient=None,
                                        decision_acceptable=None, target_acceptable=None, query_acceptable=None,
                                        binding_correct=None, cited_claims=None, supported_cited_claims=None,
                                        required_claims=None, supported_cited_required_claims=None, comment='')))
    packets.sort(key=lambda r: r['review_id'])
    write_jsonl(destination / 'review_packets.jsonl', packets)
    atomic_json(destination / 'private_mapping.json', dict(run_identity=digest(manifest['identity']), records=mapping,
                                                           packet_content_hashes={p['review_id']: digest({k:v for k,v in p.items() if k != 'review'}) for p in packets}))
    return dict(review_packets=len(packets), warning='Do not give private_mapping.json or arm identities to the reviewer.')


def rate(numerator, denominator):
    return None if denominator == 0 else numerator / denominator


def score_reviews(output, packets_path, mapping_path):
    output = Path(output)
    manifest = read_json(output / 'manifest.json')
    mapping = read_json(mapping_path)
    if mapping['run_identity'] != digest(manifest['identity']):
        raise ValueError('Review belongs to a different run')
    trials = {r['trial_id']: r for r in load_trials(output)}
    reviewed = {}
    seen = set()
    sufficient_by_case = {}
    for packet in read_jsonl(packets_path):
        rid = packet['review_id']
        if rid in seen or rid not in mapping['records']:
            raise ValueError('Duplicate/unknown review ID')
        seen.add(rid)
        if digest({k:v for k,v in packet.items() if k != 'review'}) != mapping['packet_content_hashes'][rid]:
            raise ValueError('Review task/evidence/output was changed; edit only the review field')
        info = mapping['records'][rid]
        trial = trials.get(info['trial_id'])
        if trial is None or digest(trial) != info['trial_sha256']:
            raise ValueError('Reviewed trial changed after review export')
        review = packet['review']
        if review['final'] is not True:
            continue
        if not isinstance(review['reviewer_id'], str) or not review['reviewer_id'].strip():
            raise ValueError('Final review requires reviewer identity')
        for key in ['state_sufficient', 'decision_acceptable']:
            if type(review[key]) is not bool:
                raise ValueError('Missing required semantic review: ' + key)
        for key in ['target_acceptable', 'query_acceptable', 'binding_correct']:
            if review[key] is not None and type(review[key]) is not bool:
                raise ValueError('Invalid optional semantic review')
        if trial['action'] == 'retrieve' and any(type(review[k]) is not bool for k in ['target_acceptable', 'query_acceptable']):
            raise ValueError('Retrieval action requires target and query adjudication')
        for num, den in [('supported_cited_claims', 'cited_claims'), ('supported_cited_required_claims', 'required_claims')]:
            a, b = review[num], review[den]
            if (a is None) != (b is None):
                raise ValueError('Citation numerator/denominator must be supplied together')
            if a is not None and (type(a) is not int or type(b) is not int or not 0 <= a <= b):
                raise ValueError('Invalid citation counts')
        cid = trial['case_id']
        if cid in sufficient_by_case and sufficient_by_case[cid] != review['state_sufficient']:
            raise ValueError('Identical evidence states have conflicting reference sufficiency labels; adjudicate first.')
        sufficient_by_case[cid] = review['state_sufficient']
        reviewed[trial['trial_id']] = (packet, review)
    summary = summarize_run(output)
    metrics = {}
    for arm in ['structured', 'flat']:
        arm_trials = [t for t in trials.values() if t['arm'] == arm]
        completed = [t for t in arm_trials if t['status'] == 'completed']
        judged = [(t, *reviewed[t['trial_id']]) for t in completed if t['trial_id'] in reviewed]
        stops = [(t,p,r) for t,p,r in judged if t['action'] == 'stop']
        retrievals = [(t,p,r) for t,p,r in judged if t['action'] == 'retrieve']
        correct = sum(r['decision_acceptable'] for _,_,r in judged)
        cf = [r for _,_,r in judged if r['cited_claims'] is not None]
        cc = [r for _,_,r in judged if r['required_claims'] is not None]
        bind = [r for _,_,r in judged if r['binding_correct'] is not None]
        metrics[arm] = dict(
            all_recorded_trials=len(arm_trials), valid_response_trials=len(completed), reviewed_trials=len(judged),
            unreviewed_valid_trials=len(completed) - len(judged), review_coverage=rate(len(judged), len(completed)),
            valid_response_rate=rate(len(completed), len(arm_trials)),
            reviewed_decision_accuracy=rate(correct, len(judged)),
            all_recorded_decision_accuracy=rate(correct, len(arm_trials)) if len(judged) == len(completed) else None,
            premature_stop_given_stop=rate(sum(not r['state_sufficient'] for _,_,r in stops), len(stops)),
            premature_stop_over_reviewed=rate(sum(not r['state_sufficient'] for _,_,r in stops), len(judged)),
            premature_stop_denominator=len(stops),
            unnecessary_retrieval_rate=rate(sum(r['state_sufficient'] for _,_,r in retrievals), len(retrievals)),
            target_acceptance=rate(sum(r['target_acceptable'] for _,_,r in retrievals), len(retrievals)),
            query_acceptance=rate(sum(r['query_acceptable'] for _,_,r in retrievals), len(retrievals)),
            retrieval_decisions_reviewed=len(retrievals),
            citation_faithfulness=rate(sum(r['supported_cited_claims'] for r in cf), sum(r['cited_claims'] for r in cf)),
            citation_faithfulness_denominator=sum(r['cited_claims'] for r in cf), citation_reviewed_trials=len(cf),
            citation_completeness=rate(sum(r['supported_cited_required_claims'] for r in cc), sum(r['required_claims'] for r in cc)),
            citation_completeness_denominator=sum(r['required_claims'] for r in cc),
            binding_correctness=rate(sum(r['binding_correct'] for r in bind), len(bind)), binding_reviewed_trials=len(bind),
            stop_answer_em=rate(sum(squad_em(t['parsed']['decision']['answer'], p['reference']['answer']) for t,p,_ in stops), len(stops)),
            stop_answer_f1=rate(sum(squad_f1(t['parsed']['decision']['answer'], p['reference']['answer']) for t,p,_ in stops), len(stops)))
    paired = {}
    for trial_id, (_, review) in reviewed.items():
        trial = trials[trial_id]
        paired.setdefault(trial['case_id'], {})[trial['arm']] = (trial['source_question_id'], int(review['decision_acceptable']))
    by_question = {}
    for pair in paired.values():
        if set(pair) == {'structured', 'flat'}:
            qid = pair['structured'][0]
            by_question.setdefault(qid, []).append(pair['structured'][1] - pair['flat'][1])
    deltas = [sum(values) / len(values) for values in by_question.values()]
    bootstrap = None
    if len(deltas) >= 2:
        rng = random.Random(42)
        means = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(2000))
        bootstrap = dict(question_count=len(deltas), paired_state_count=sum(map(len, by_question.values())),
                         macro_difference=sum(deltas) / len(deltas), interval_95=[means[49], means[1949]],
                         method='paired question-cluster bootstrap, 2000 draws; reviewed pairs only')
    result = dict(run=summary, metrics=metrics, paired_comparison=bootstrap,
                  evaluation_complete=summary['execution_complete'] and len(reviewed) == sum(t['status']=='completed' for t in trials.values()),
                  scope='Controlled one-step decisions. Stop-answer EM is conditional, NOT full-RAG answer accuracy.',
                  supporting_fact_coverage='Fixed by each evidence state and identical across arms; not a retrieval improvement.',
                  review_scope='Human/independent adjudication supplied by user; runtime model judgments are not gold.',
                  development_only=manifest['role'] == 'development')
    atomic_json(output / 'evaluation.json', result)
    return result
