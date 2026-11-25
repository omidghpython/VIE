"""Cited node answers and bounded rechecks; gold labels never enter prompts."""
import json
from ..retriever import format_evidence


def standard_sufficiency_check(llm, question, evidence):
    data = llm.ask_json(
        'Decide whether the evidence contains all facts needed to answer the question. '
        'Use no outside knowledge. If facts are missing, propose a focused follow-up query. '
        'Return JSON: {"is_sufficient": true, "follow_up_query": "..."}\n'
        f'Question:\n{question}\nEvidence:\n{format_evidence(evidence)}')
    if set(data) != {'is_sufficient', 'follow_up_query'} or type(data['is_sufficient']) is not bool or not isinstance(data['follow_up_query'], str):
        raise ValueError('Invalid sufficiency response; no defaults substituted.')
    data['follow_up_query'] = data['follow_up_query'].strip() or question
    return data


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def citation_map(evidence):
    sources = {}
    for passage in evidence:
        ids, sentences = passage['sentence_ids'], passage['sentences']
        if len(ids) != len(sentences):
            raise ValueError('Evidence sentence IDs/text differ in length.')
        for sid, sentence in zip(ids, sentences):
            ref = f"{passage['index']}:{sid}"
            if ref in sources:
                raise ValueError('Duplicate evidence reference: ' + ref)
            sources[ref] = {'title': passage['title'], 'sentence': sentence}
    return sources


def validate_refs(refs, evidence):
    sources = citation_map(evidence)
    if (not isinstance(refs, list) or not refs or
            not all(isinstance(ref, str) and ref in sources for ref in refs)):
        raise ValueError('Answer must cite existing sentence IDs from the supplied evidence.')
    return list(dict.fromkeys(refs))


def assess_node(llm, question, answer_type, evidence, *, original_question='',
                bindings=None, review=False, prior_need='', prior_error=''):
    prompt = ('Answer Node using only Evidence and its dependency Bindings. '
              'Keep each entity attached to its property/value. Resolve slots using Bindings. '
              'Explicit facts, supported negative answers, and simple logical/date comparisons count. '
              'Cite the supporting sentence IDs, including premises used for inference. '
              'Return compact JSON: {"answer":"short value","refs":["0:1"],"need":""}. '
              'If unsupported: answer="", refs=[], need=a specific missing-fact query. '
              'A citation must support the answer, not just mention its entity. No outside facts.\n')
    if review:
        prompt += ('TARGETED RECHECK (one pass): inspect explicit dates, aliases, relation direction '
                   'and comparisons before abstaining. Do not require unrelated details or confuse '
                   'a supported no with missing evidence. Prior need: ' + prior_need + '\n')
        if prior_error:
            prompt += 'Previous response error: ' + prior_error + '\n'
    prompt += ('Original question:\n' + original_question + '\nNode:\n' + question +
               '\nAnswer type: ' + answer_type + '\nBindings:\n' + compact(bindings or {}) +
               '\nEvidence:\n' + format_evidence(evidence))
    try:
        data = llm.ask_json(prompt)
        if (not isinstance(data, dict) or set(data) != {'answer', 'refs', 'need'}
                or not isinstance(data['answer'], str) or not isinstance(data['need'], str)
                or not isinstance(data['refs'], list)):
            raise ValueError('Invalid cited answer schema.')
        answer = data['answer'].strip()
        refs = validate_refs(data['refs'], evidence) if answer else []
        if not answer and data['refs']:
            raise ValueError('An unanswered node must have empty refs.')
        return {'sufficient': bool(answer), 'answer': answer, 'refs': refs,
                'missing_query': data['need'].strip() or question, 'error': ''}
    except ValueError as exc:
        # An invalid assessment is recorded and can receive one targeted review.
        return {'sufficient': False, 'answer': '', 'refs': [], 'missing_query': question,
                'error': str(exc)}


def audit_cached_bindings(llm, question, bindings, evidence):
    """One joint audit instead of regenerating every previously answered node.

    Code checks citation existence. Support/conflict is still a model judgment.
    """
    prompt = ('Audit cached Bindings against all Evidence. Preserve supported answers; '
              'flag only an unsupported answer or a contradiction. Keep entity/property identity. '
              'Do not regenerate answers. Return compact JSON: '
              '{"invalid":[{"id":"q1","refs":["0:1"],"reason":"specific conflict"}]}. '
              'Use invalid=[] when all bindings remain supported. Cite evidence for each conflict.\n'
              'Original question:\n' + question + '\nBindings:\n' + compact(bindings) +
              '\nEvidence:\n' + format_evidence(evidence))
    try:
        data = llm.ask_json(prompt)
        if not isinstance(data, dict) or set(data) != {'invalid'} or not isinstance(data['invalid'], list):
            raise ValueError('Invalid cache audit schema.')
        seen = set()
        for entry in data['invalid']:
            if (not isinstance(entry, dict) or set(entry) != {'id', 'refs', 'reason'}
                    or not isinstance(entry['id'], str) or entry['id'] not in bindings
                    or entry['id'] in seen or not isinstance(entry['reason'], str)
                    or not entry['reason'].strip()):
                raise ValueError('Invalid cache conflict.')
            entry['refs'] = validate_refs(entry['refs'], evidence)
            seen.add(entry['id'])
        return {'invalid_ids': sorted(seen), 'conflicts': data['invalid'], 'status': 'reviewed'}
    except ValueError as exc:
        return {'invalid_ids': list(bindings), 'conflicts': [], 'status': 'invalid', 'error': str(exc)}
