"""Deterministic structural observer. Never changes either experimental arm's decision.

This is a prototype for a later closed-loop controller, not independent semantic verification.
"""
from .prompts import task_view


def structural_observation(case, assessment, remaining_retrievals=None):
    tasks, graph = task_view(case)
    by_id = {t['task_id']: t for t in tasks}
    dependencies = {task_id: set() for task_id in by_id}
    for edge in graph['edges']:
        dependencies[edge['consumer']].add(edge['producer'])
    rows = {r['task_id']: r for r in assessment['assessments']}
    supported, pending, events = set(), set(by_id), []
    while pending:
        ready = sorted(t for t in pending if not (dependencies[t] & pending))
        if not ready:
            raise ValueError('Cycle in validated plan')
        for task_id in ready:
            missing = sorted(dependencies[task_id] - supported)
            declared = rows[task_id]['status']
            effective = 'blocked' if missing else declared
            if effective == 'supported':
                supported.add(task_id)
            events.append(dict(task_id=task_id, declared_status=declared, structural_status=effective,
                               missing_dependencies=missing,
                               supported_without_supported_prerequisites=bool(missing and declared == 'supported')))
            pending.remove(task_id)
    frontier = [t for t in by_id if t not in supported and dependencies[t] <= supported]
    def downstream_count(task):
        reached = {task}
        while True:
            more = {t for t, deps in dependencies.items() if deps & reached}
            if more <= reached:
                return len(reached) - 1
            reached |= more
    frontier.sort(key=lambda t: (-downstream_count(t), t))
    decision = assessment['decision']
    if graph['root'] in supported and decision['action'] == 'stop':
        suggested, target, reason = 'stop', None, 'model_goal_support_plus_structural_closure'
    elif remaining_retrievals is not None and remaining_retrievals <= 0:
        suggested, target, reason = 'abstain', None, 'budget_exhausted'
    elif frontier:
        suggested, target, reason = 'retrieve', frontier[0], 'ready_unresolved_prerequisite'
    else:
        suggested, target, reason = 'abstain', None, 'unresolved_original_goal'
    return dict(events=events, frontier=frontier, suggested_action=suggested,
                target_task_id=target, reason=reason,
                query=(rows[target]['missing_fact'].strip() or by_id[target]['question']) if target else '',
                model_stop_without_structural_closure=decision['action'] == 'stop' and graph['root'] not in supported,
                semantic_support_verified=False, observer_only=True)


def invalidate_descendants(graph, changed):
    invalid = set(changed)
    while True:
        extra = {e['consumer'] for e in graph['edges'] if e['producer'] in invalid}
        if extra <= invalid:
            return invalid
        invalid |= extra
