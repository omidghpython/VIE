"""Public runtime records and private evaluation labels are separate files.

Gold-guided evidence deletion is benchmark construction, NOT a retrieval result.
No state is automatically labeled semantically sufficient from gold coverage.
"""
from __future__ import annotations
import json
import zipfile
from .common import ROOT, atomic_json, digest, read_json, read_jsonl, question_digest, write_jsonl, verify_baseline
from hotpotqa_operadic_rag.contracts import validate_plan

CONDITIONS = ('full_context', 'empty', 'support_removed', 'one_support_retained', 'distractor_documents')


def context_sentences(sample):
    context = sample['context']
    pairs = zip(context['title'], context['sentences']) if isinstance(context, dict) else context
    return [dict(ref=f'p{pi}:s{si}', title=title, sentence_id=si, text=text)
            for pi, (title, sentences) in enumerate(pairs) for si, text in enumerate(sentences)]


def support_pairs(sample):
    facts = sample['supporting_facts']
    return list(zip(facts['title'], facts['sent_id'])) if isinstance(facts, dict) else [tuple(f) for f in facts]


def select_evidence(all_evidence, gold, condition):
    gold = set(gold)
    titles = {title for title, _ in gold}
    is_gold = lambda item: (item['title'], item['sentence_id']) in gold
    if condition == 'full_context':
        return list(all_evidence)
    if condition == 'empty':
        return []
    if condition == 'support_removed':
        return [item for item in all_evidence if not is_gold(item)]
    if condition == 'distractor_documents':
        return [item for item in all_evidence if item['title'] not in titles]
    if condition == 'one_support_retained':
        first = next((item['ref'] for item in all_evidence if is_gold(item)), None)
        return [item for item in all_evidence if not is_gold(item) or item['ref'] == first]
    raise ValueError('Unknown evidence condition')


def build_development():
    identity = verify_baseline()
    samples = read_json(ROOT / 'private/original_samples.json')
    with zipfile.ZipFile(ROOT / 'provenance/max4_results.zip') as archive:
        records = {row['question_id']: row for name in archive.namelist()
                   if '/questions/' in name and name.endswith('.json')
                   for row in [json.loads(archive.read(name))]}
    cases, labels, questions = [], [], []
    for order, sample in enumerate(samples, 1):
        qid = sample.get('id', sample.get('question_id'))
        phase = records[qid]['phases']['structure']
        saved = phase.get('result') or {}
        plan = saved.get('plan')
        valid = phase['status'] == 'valid'
        if valid:
            # Validate without rewriting the stored tree, questions, types, or dependencies.
            validate_plan(plan, max_nodes=4)
        elif plan is not None:
            # Preserve any invalid candidate as historical data; never silently repair it.
            try:
                validate_plan(plan, max_nodes=4)
            except ValueError:
                pass
        gold = support_pairs(sample)
        evidence = context_sentences(sample)
        questions.append(dict(question_id=qid, question_sha256=question_digest(sample['question']),
                              order=order, type=sample['type'], structure_status=phase['status'],
                              plan_sha256=digest(plan), recorded_generation_cost=phase['telemetry']))
        for condition in CONDITIONS:
            visible = select_evidence(evidence, gold, condition)
            case_id = digest([qid, condition, 'v1'])[:24]
            cases.append(dict(schema_version=1, case_id=case_id, source_question_id=qid,
                              split='development', question=sample['question'], question_type=sample['type'],
                              plan=plan, plan_sha256=digest(plan), structure_valid=valid, evidence=visible))
            visible_gold = sum((item['title'], item['sentence_id']) in set(gold) for item in visible)
            labels.append(dict(case_id=case_id, source_question_id=qid, order=order,
                               condition=condition, answer=sample['answer'], supporting_facts=gold,
                               visible_gold_coverage=visible_gold / len(set(gold)) if gold else None,
                               reference_action=None, acceptable_targets=None, semantic_review='pending',
                               warning='Coverage is not semantic sufficiency; manual reference decision required.'))
    assert len(questions) == 40 and sum(q['structure_status'] == 'valid' for q in questions) == 37
    write_jsonl(ROOT / 'data/development_cases.jsonl', cases)
    write_jsonl(ROOT / 'private/development_labels.jsonl', labels)
    existing_registry = read_json(ROOT/'data/split_registry.json') if (ROOT/'data/split_registry.json').exists() else {}
    atomic_json(ROOT / 'data/split_registry.json', dict(development=questions, heldout=existing_registry.get('heldout', [])))
    atomic_json(ROOT / 'data/development_manifest.json', dict(
        schema_version=1, split='development', baseline=identity['baseline'],
        cases_sha256=digest(cases), labels_sha256=digest(labels), questions_sha256=digest(questions),
        question_count=40, case_count=len(cases), valid_questions=37, invalid_questions=3,
        conditions=list(CONDITIONS), evidence_origin='HotpotQA context; controlled offline evidence deletion',
        independent_semantic_labels='pending', retrieval_executed=False,
        generalization_claim_permitted=False))
    return {'questions': 40, 'states': len(cases), 'valid_questions': 37, 'invalid_questions': 3}


def validate_case(case):
    required = {'schema_version', 'case_id', 'source_question_id', 'split', 'question', 'question_type',
                'plan', 'plan_sha256', 'structure_valid', 'evidence'}
    if set(case) != required:
        raise ValueError('Runtime case has missing/extra fields; gold and construction labels are forbidden.')
    if case['split'] not in {'development', 'heldout'} or case['schema_version'] != 1:
        raise ValueError('Invalid dataset role/schema')
    if not isinstance(case['question'], str) or not case['question'].strip():
        raise ValueError('Missing question')
    if digest(case['plan']) != case['plan_sha256']:
        raise ValueError('Plan fingerprint differs')
    refs = set()
    for item in case['evidence']:
        if set(item) != {'ref', 'title', 'sentence_id', 'text'}:
            raise ValueError('Invalid evidence schema')
        if not all(isinstance(item[k], str) and item[k].strip() for k in ['ref', 'title']) or not isinstance(item['text'], str):
            raise ValueError('Empty evidence field')
        if type(item['sentence_id']) is not int or item['sentence_id'] < 0 or item['ref'] in refs:
            raise ValueError('Duplicate ref or invalid sentence index')
        refs.add(item['ref'])
    if type(case['structure_valid']) is not bool:
        raise ValueError('structure_valid must be boolean')
    if case['structure_valid']:
        validate_plan(case['plan'], max_nodes=4)


def validate_split(cases, role, registry):
    development = registry['development']
    registered = {q['question_id']: q for q in development}
    ids = {q['question_id'] for q in development}
    hashes = {q['question_sha256'] for q in development}
    heldout = {q['question_id']:q for q in registry.get('heldout', [])}
    seen = set()
    for case in cases:
        validate_case(case)
        if case['case_id'] in seen:
            raise ValueError('Duplicate case ID')
        seen.add(case['case_id'])
        if case['split'] != role:
            raise ValueError('Mixed or misdeclared dataset roles')
        if role == 'development':
            baseline = registered.get(case['source_question_id'])
            if baseline is None:
                raise ValueError('Development case is not in the frozen registry')
            if (baseline['question_sha256'] != question_digest(case['question']) or
                    baseline['plan_sha256'] != case['plan_sha256'] or
                    (baseline['structure_status'] == 'valid') != case['structure_valid']):
                raise ValueError('Stored development question/tree/status changed')
        if role == 'heldout' and (case['source_question_id'] in ids or question_digest(case['question']) in hashes):
            raise ValueError('Development question cannot be used as heldout evaluation')
        if role == 'heldout':
            registered_final = heldout.get(case['source_question_id'])
            if registered_final is None or registered_final['question_sha256'] != question_digest(case['question']):
                raise ValueError('Heldout question is not part of the registered final set')


def register_holdout(input_path, output_path):
    rows = read_jsonl(input_path)
    registry = read_json(ROOT / 'data/split_registry.json')
    ids = {q['question_id'] for q in registry['development']}
    hashes = {q['question_sha256'] for q in registry['development']}
    registered = []
    for row in rows:
        qid, qhash = row['question_id'], question_digest(row['question'])
        if qid in ids or qhash in hashes:
            raise ValueError('Duplicate/development question in candidate heldout set: ' + qid)
        ids.add(qid); hashes.add(qhash)
        registered.append(dict(question_id=qid, question_sha256=qhash))
    if not registered:
        raise ValueError('Empty heldout set')
    atomic_json(output_path, dict(role='candidate_heldout', questions=registered,
                                 input_sha256=digest(rows), note='Registration only; not an executed evaluation.'))
    return len(registered)
