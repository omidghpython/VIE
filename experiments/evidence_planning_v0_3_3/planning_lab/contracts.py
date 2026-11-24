import json
from .prompts import task_view


def parse_decision(raw, case):
    def reject_duplicate(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Non-finite JSON constant: ' + value)
    data = json.loads(raw, object_pairs_hook=reject_duplicate, parse_constant=reject_constant)
    if not isinstance(data, dict) or set(data) != {'assessments', 'decision'}:
        raise ValueError('Wrong decision envelope')
    tasks, _ = task_view(case)
    task_ids = {t['task_id'] for t in tasks}
    refs = {e['ref'] for e in case['evidence'] if e['text'].strip()}
    def check_refs(value):
        if not isinstance(value, list) or any(not isinstance(x, str) or x not in refs for x in value):
            raise ValueError('Unknown or malformed evidence reference')
        if len(value) != len(set(value)):
            raise ValueError('Duplicate evidence refs')
    if not isinstance(data['assessments'], list):
        raise ValueError('Assessments must be a list')
    seen = set()
    for row in data['assessments']:
        keys = {'task_id', 'status', 'answer', 'refs', 'entity', 'property', 'missing_fact'}
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError('Wrong assessment fields')
        if any(not isinstance(row[k], str) for k in keys - {'refs'}):
            raise ValueError('Assessment fields must be strings')
        if row['task_id'] not in task_ids or row['task_id'] in seen:
            raise ValueError('Duplicate/unknown task')
        seen.add(row['task_id'])
        check_refs(row['refs'])
        if row['status'] not in {'supported', 'insufficient', 'blocked', 'conflicted', 'unknown'}:
            raise ValueError('Invalid support status')
        if row['status'] == 'supported':
            if not row['answer'].strip() or not row['refs'] or not row['entity'].strip() or not row['property'].strip():
                raise ValueError('Supported task requires answer, refs, entity and property')
        elif row['answer'].strip():
            raise ValueError('Unsupported answer must be empty')
    if seen != task_ids:
        raise ValueError('Missing task assessment')
    decision = data['decision']
    if not isinstance(decision, dict) or set(decision) != {'action', 'answer', 'refs', 'target_task_ids', 'query', 'reason'}:
        raise ValueError('Wrong decision fields')
    if any(not isinstance(decision[k], str) for k in ['action', 'answer', 'query', 'reason']):
        raise ValueError('Decision fields must be strings')
    check_refs(decision['refs'])
    targets = decision['target_task_ids']
    if not isinstance(targets, list) or any(not isinstance(t, str) or t not in task_ids for t in targets):
        raise ValueError('Invalid retrieval target')
    if len(set(targets)) != len(targets) or not decision['reason'].strip():
        raise ValueError('Duplicate targets or empty reason')
    action = decision['action']
    if action == 'stop':
        if not decision['answer'].strip() or not decision['refs'] or decision['query'].strip() or targets:
            raise ValueError('Invalid stop action')
    elif action == 'retrieve':
        if decision['answer'].strip() or not decision['query'].strip() or not targets:
            raise ValueError('Invalid retrieval action')
    elif action == 'abstain':
        if decision['answer'].strip() or decision['query'].strip() or targets:
            raise ValueError('Invalid abstention')
    else:
        raise ValueError('Unknown action')
    return data
