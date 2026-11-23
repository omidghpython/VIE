"""Cited tree execution, entity/property bindings and one targeted review pass."""
from ..contracts import SLOT_PATTERN, expand_plan
from ..decomposition import decompose_question
from ..retriever import retrieve_round, merge_evidence
from ..llm import require_short_answer
from .common import assess_node, audit_cached_bindings, citation_map


def ancestor_bindings(node, by_id, bindings):
    needed = set()
    def visit(nid):
        if nid in needed:
            return
        needed.add(nid)
        for dep in by_id[nid]['dependencies']:
            visit(dep)
    for dep in node['dependencies']:
        visit(dep)
    return {nid: value for nid, value in bindings.items() if nid in needed}


def evaluate_tree(llm, plan, evidence, *, original_question='', previous=None,
                  previous_evidence=None, review=False):
    by_id = {node['id']: node for node in plan['nodes']}
    sources = citation_map(evidence)
    bindings = dict(previous.get('bindings', {})) if previous else {}
    old_states = {s['id']: s for s in previous['nodes']} if previous else {}
    invalid = set()
    old_sources = citation_map(previous_evidence or [])
    for nid, binding in bindings.items():
        if (binding['source_question'] != by_id[nid]['question'] or
                binding['answer_type'] != by_id[nid]['answer_type'] or
                any(ref not in sources or sources[ref] != old_sources.get(ref) for ref in binding['refs'])):
            invalid.add(nid)
    audit = None
    if bindings and sources != old_sources:
        eligible = {nid: b for nid, b in bindings.items() if nid not in invalid}
        if eligible:
            audit = audit_cached_bindings(llm, original_question, eligible, evidence)
            invalid.update(audit['invalid_ids'])
    for node in plan['nodes']:
        if set(node['dependencies']) & invalid:
            invalid.add(node['id'])
    for nid in invalid:
        bindings.pop(nid, None)

    expanded, states = {}, []
    for node in plan['nodes']:
        nid = node['id']
        expanded[nid] = SLOT_PATTERN.sub(lambda m: '[' + expanded[m.group(1)] + ']', node['question'])
        missing = [dep for dep in node['dependencies'] if dep not in bindings]
        if missing:
            states.append({'id': nid, 'status': 'blocked', 'answer': '', 'missing_dependencies': missing,
                           'question': node['question'], 'missing_query': expanded[nid], 'refs': [],
                           'reused': False, 'review': review})
            continue
        if nid in bindings:
            binding = bindings[nid]
            states.append({'id': nid, 'status': 'answered', 'question': node['question'],
                           'answer': binding['value'], 'refs': binding['refs'], 'missing_query': '',
                           'reused': True, 'review': False})
            continue
        inputs = ancestor_bindings(node, by_id, bindings)
        result = assess_node(llm, node['question'], node['answer_type'], evidence,
                             original_question=original_question, bindings=inputs, review=review,
                             prior_need=old_states.get(nid, {}).get('missing_query', ''),
                             prior_error=old_states.get(nid, {}).get('error', ''))
        if result['sufficient']:
            # Preserve question/entity/property identity and all ancestral sources.
            refs = list(dict.fromkeys(result['refs'] + [ref for b in inputs.values() for ref in b['refs']]))
            bindings[nid] = {'source_question': node['question'], 'answer_type': node['answer_type'],
                             'value': result['answer'], 'refs': refs}
        states.append({'id': nid, 'status': 'answered' if result['sufficient'] else 'insufficient',
                       'question': node['question'], 'answer': result['answer'], 'refs': result['refs'],
                       'missing_query': '' if result['sufficient'] else result['missing_query'],
                       'error': result['error'], 'reused': False, 'review': review,
                       'support': [dict(ref=ref, **sources[ref]) for ref in result['refs']]})
    return {'nodes': states, 'bindings': bindings,
            'answers': {nid: b['value'] for nid, b in bindings.items()},
            'sufficient': plan['final'] in bindings, 'cache_audit': audit}


def joint_query(question, needs):
    unique = list(dict.fromkeys(text.strip() for text in needs if text.strip()))
    return question + '\nInformation needed:\n' + '\n'.join(unique)


def run_operadic_rag(question, retriever, llm, tracker):
    plan, decomposition_trace = decompose_question(llm, question)
    leaves = [node['question'] for node in plan['nodes'] if not node['dependencies']]
    first, retrieval1 = retrieve_round(retriever, joint_query(question, leaves), tracker)
    round1 = evaluate_tree(llm, plan, first, original_question=question)
    evidence, retrieval_trace, rounds = list(first), [retrieval1], [round1]
    second_query = ''
    if not round1['sufficient']:
        needs = [node['missing_query'] for node in round1['nodes'] if node['status'] != 'answered']
        second_query = joint_query(question, needs)
        second, retrieval2 = retrieve_round(retriever, second_query, tracker, previous=first)
        evidence = merge_evidence(first, second)
        retrieval_trace.append(retrieval2)
        rounds.append(evaluate_tree(llm, plan, evidence, original_question=question,
                                    previous=round1, previous_evidence=first))
    if not rounds[-1]['sufficient']:
        # Exactly one targeted pass. No extra retrieval or unbounded retries.
        rounds.append(evaluate_tree(llm, plan, evidence, original_question=question,
                                    previous=rounds[-1], previous_evidence=evidence, review=True))
    final_round = rounds[-1]
    answer, answer_source = '', 'unresolved_tree'
    if final_round['sufficient']:
        root = final_round['bindings'][plan['final']]
        if len(root['value'].split()) <= 5:
            answer = require_short_answer(root['value'])
            answer_source = 'cited_root'
        else:
            answer = llm.shorten_answer(question, evidence, final_round['bindings'], plan['final'])
            answer_source = 'shortened_root'
    return {'answer_decomposed': answer, 'plan': plan, 'expanded_plan': expand_plan(plan),
            'decomposition_trace': decomposition_trace, 'structural_status': 'valid',
            'semantic_status': 'model_reviewed', 'semantic_review_independent': False,
            'node_rounds': rounds, 'final_evidence_sufficient': final_round['sufficient'],
            'answer_status': 'answered' if answer else 'abstained', 'answer_source': answer_source,
            'reused_nodes': sum(s['reused'] for r in rounds for s in r['nodes']),
            'targeted_review_calls': sum(s['review'] and s['status'] != 'blocked' and not s['reused']
                                         for r in rounds for s in r['nodes']),
            'stopped_after_first': round1['sufficient'], 'second_query': second_query,
            'evidence_first': first, 'evidence_final': evidence, 'retrieval_trace': retrieval_trace}
