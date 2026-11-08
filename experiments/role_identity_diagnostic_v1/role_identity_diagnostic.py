"""Read-only, English pattern diagnostics; never a semantic validity certificate.

Statuses describe only same-person role binding, not relation correctness,
candidate completeness, evidence support or answer accuracy. No model calls.
"""
import re
from collections import Counter

VERSION = '1.0.0'
ROLES = frozenset(('actor actress author writer director singer vocalist composer '
                   'founder politician photographer cinematographer').split())
ROLE_PATTERN = '(?:' + '|'.join(sorted(ROLES)) + ')'
SLOT = re.compile(r'\{\{(q[1-9][0-9]*)\}\}')
TYPES = {'person', 'organization', 'place', 'date', 'number', 'work', 'boolean', 'other'}


def _text(value):
    # Titles are data, not evidence of the question's requested roles.
    return ' '.join(re.sub(r'"[^"\n]*"', ' ', value.casefold()).split())


def _target(question):
    text = _text(question)
    if re.match(r'^(?:can|could|would|will) you\b', text):
        return None
    wh = re.search(r'\b(?:what|which)\b', text)
    if not wh:
        return None
    tail = text[wh.end():].strip()
    # This narrow surface pattern is a candidate, NOT proof of coreference.
    pair = re.match(rf'^({ROLE_PATTERN}) and ({ROLE_PATTERN})\b(.*)$', tail)
    distinct = re.match(
        rf'^({ROLE_PATTERN}) and (?:which|what|the|a|an|another) ({ROLE_PATTERN})\b', tail)
    if distinct:
        return {'roles': list(distinct.groups()), 'form': 'explicit_distinct'}
    if not pair or pair[1] == pair[2]:
        return None
    suffix = pair[3].strip()
    if re.match(r'^(?:are|were|have|do)\b', suffix):
        return {'roles': [pair[1], pair[2]], 'form': 'plural_coordination'}
    if re.match(r'^(?:is|was|has|does|did|who|that)\b', suffix) or suffix in {'', '?', '.', '!'}:
        return {'roles': [pair[1], pair[2]], 'form': 'singular_coordination_candidate'}
    return None


def _graph(plan):
    """Validate enough of the strict-tree contract to make diagnostics meaningful."""
    if not isinstance(plan, dict) or not isinstance(plan.get('nodes'), list):
        return None
    nodes = plan['nodes']
    if not 1 <= len(nodes) <= 128:
        return None
    by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            return None
        nid, question, deps = node.get('id'), node.get('question'), node.get('dependencies')
        kind = node.get('answer_type')
        if (not isinstance(nid, str) or not re.fullmatch(r'q[1-9][0-9]*', nid)
                or nid in by_id or not isinstance(question, str) or not question.strip()
                or not isinstance(deps, dict) or not isinstance(kind, str) or kind not in TYPES):
            return None
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in deps.items()):
            return None
        slots = Counter(SLOT.findall(question))
        if (set(slots) != set(deps) or any(n != 1 for n in slots.values())
                or any(c in SLOT.sub('', question) for c in '{}')):
            return None
        by_id[nid] = node
    final = plan.get('final')
    if not isinstance(final, str) or final not in by_id:
        return None
    consumers = Counter()
    for node in nodes:
        for dep, kind in node['dependencies'].items():
            if dep not in by_id or dep == node['id'] or by_id[dep]['answer_type'] != kind:
                return None
            consumers[dep] += 1
    if consumers[final] or any(consumers[n] != 1 for n in by_id if n != final):
        return None
    resolved = set()
    while len(resolved) < len(nodes):
        ready = {n for n, node in by_id.items() if n not in resolved
                 and set(node['dependencies']) <= resolved}
        if not ready:
            return None
        resolved.update(ready)
    return by_id


def _leaf_role(node):
    if node['dependencies'] or node['answer_type'] != 'person':
        return None
    if _target(node['question']) is not None:
        return None  # A joint target is not a separate single-role candidate.
    match = re.match(rf'^(?:which|what) ({ROLE_PATTERN})\b', _text(node['question']))
    return match[1] if match else None


def diagnose(question, plan):
    """Return a new diagnostic object; never alter/repair the supplied plan.

    suspicious: an observed shape needs human review; not a definitive rejection.
    no_violation_found: a supported pattern passed this limited check only.
    unknown: insufficient or unsupported syntax/structure. Never equate to valid.
    """
    def result(status, reason, nodes=(), target=None):
        return {'version': VERSION, 'status': status, 'reason': reason,
                'node_ids': list(nodes), 'target': target, 'advisory_only': True}

    if not isinstance(question, str) or not question.strip():
        return result('unknown', 'invalid_question')
    graph = _graph(plan)
    if graph is None:
        return result('unknown', 'invalid_or_unsupported_tree')
    target = _target(question)
    if target is None:
        return result('unknown', 'unsupported_or_non_role_target')
    roles = target['roles']
    root = graph[plan['final']]
    root_text = _text(root['question'])
    if target['form'] != 'singular_coordination_candidate':
        joint = _target(root['question'])
        if (joint and joint['form'] == 'singular_coordination_candidate'
                and set(joint['roles']) == set(roles)):
            return result('suspicious', 'distinct_people_collapsed_to_joint_target',
                          [root['id']], target)
        return result('no_violation_found', 'distinct_people_not_forced_into_one', target=target)
    # Keep the answer target even when a node carries a misleading person label.
    if (root['answer_type'] == 'boolean'
            or re.match(r'^(?:is|are|was|were|do|does|did|has|have|had|can|could|would|will)\b', root_text)):
        return result('suspicious', 'person_target_replaced_by_boolean', [root['id']], target)
    if root['answer_type'] != 'person':
        return result('suspicious', 'person_target_has_nonperson_label', [root['id']], target)

    role_leaves = {role: [n for n in graph.values() if _leaf_role(n) == role] for role in roles}
    if all(role_leaves.values()):
        # Ambiguous branch assignments and non-direct compositions are left alone.
        if any(len(v) != 1 for v in role_leaves.values()):
            return result('unknown', 'multiple_candidate_branches', target=target)
        ids = [role_leaves[r][0]['id'] for r in roles]
        if set(root['dependencies']) != set(ids):
            return result('unknown', 'indirect_role_composition', ids, target)
        for ordered in (ids, ids[::-1]):
            slots = [re.escape('{{' + n + '}}') for n in ordered]
            pattern = (r'which person is (?:common to|in both) ' + slots[0]
                       + r' and ' + slots[1] + r'\??')
            if re.fullmatch(pattern, root_text):
                return result('no_violation_found', 'explicit_shared_person_composition',
                              ids + [root['id']], target)
        return result('suspicious', 'parallel_role_candidates_need_identity_review',
                      ids + [root['id']], target)

    # A single node carrying both roles passes only the role-preservation check.
    joint = _target(root['question'])
    if (not root['dependencies'] and joint
            and joint['form'] == 'singular_coordination_candidate'
            and set(joint['roles']) == set(roles)):
        return result('no_violation_found', 'roles_kept_in_one_person_question', [root['id']], target)

    # A person-valued filter over the SAME supplied candidate, not a yes/no check.
    if len(root['dependencies']) == 1:
        dep = next(iter(root['dependencies']))
        leaf_role = _leaf_role(graph[dep])
        if leaf_role in roles:
            other = next(r for r in roles if r != leaf_role)
            slot = re.escape('{{' + dep + '}}')
            pattern = (rf'(?:which|what) (?:person|{leaf_role}) (?:among|from) '
                       + slot + rf' is (?:also )?(?:a |an )?{other}\??')
            if re.fullmatch(pattern, root_text):
                return result('no_violation_found', 'same_candidate_person_filter',
                              [dep, root['id']], target)
    return result('unknown', 'unrecognized_role_composition', [root['id']], target)
