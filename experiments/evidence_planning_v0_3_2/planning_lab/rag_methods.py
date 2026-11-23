"""Original Standard/max4 execution and a new active dependency controller."""
import copy
from types import FunctionType
from .common import digest
from .rag_support import check_support, stop_gate
from hotpotqa_operadic_rag.contracts import SLOT_PATTERN, validate_plan
from hotpotqa_operadic_rag.methods.standard import run_standard_rag
from hotpotqa_operadic_rag.methods.operadic import run_operadic_rag, ancestor_bindings
from hotpotqa_operadic_rag.methods.common import assess_node
from hotpotqa_operadic_rag.retriever import retrieve_round, merge_evidence


def standard(question, plan, retriever, llm, session):
    result = run_standard_rag(question, retriever, llm, session)
    return dict(answer=result['answer_std'], status='answered' if result['answer_std'] else 'abstained',
                citations_native=[], evidence_final=result['evidence_final'], details=result,
                stop_basis='original_standard_policy')


def max4(question, plan, retriever, llm, session):
    validate_plan(plan, max_nodes=4)
    # Inject only the frozen decomposition in a private function namespace.
    # The original function bytecode, globals and source files are not changed.
    namespace = dict(run_operadic_rag.__globals__)
    namespace['decompose_question'] = lambda _llm, _question: (copy.deepcopy(plan), [])
    execute = FunctionType(run_operadic_rag.__code__, namespace, name=run_operadic_rag.__name__,
                           argdefs=run_operadic_rag.__defaults__, closure=run_operadic_rag.__closure__)
    result = execute(question, retriever, llm, session)
    final = result['node_rounds'][-1]['bindings'].get(plan['final'],{})
    return dict(answer=result['answer_decomposed'], status='answered' if result['answer_decomposed'] else 'abstained',
                citations_native=final.get('refs',[]), evidence_final=result['evidence_final'], details=result,
                stop_basis='original_max4_executor_with_frozen_plan')


def frontier(plan, bindings):
    ready = [n for n in plan['nodes'] if n['id'] not in bindings and set(n['dependencies']) <= set(bindings)]
    def downstream(node):
        reached = {node['id']}
        while True:
            extra = {n['id'] for n in plan['nodes'] if set(n['dependencies']) & reached}
            if extra <= reached:
                return len(reached)
            reached |= extra
    return sorted(ready, key=lambda n: (-downstream(n), n['id']))


def retrieval_target(plan, bindings, attempts):
    """Give every currently ready unresolved node a turn before retrying one.

    Stable ties retain the original downstream-priority / node-ID ordering.
    Counts concern successful targeted retrievals, not model assessments; a
    blocked node is never made ready by this scheduling rule.
    """
    ready = frontier(plan, bindings)
    return min(ready, key=lambda n: attempts.get(n['id'], 0)) if ready else None


def operadic(question, plan, retriever, llm, session):
    ordered = validate_plan(plan, max_nodes=4)
    if ordered != plan:
        # Validation may return canonical order, but the stored tree is never edited.
        plan = ordered
    by_id = {n['id']:n for n in plan['nodes']}
    evidence, bindings, rounds = [], {}, []
    needs = {}
    retrieval_attempts = {}
    while True:
        target = retrieval_target(plan, bindings, retrieval_attempts)
        if target is None:
            return dict(answer='',status='abstained',citations_native=[],evidence_final=evidence,
                        details={'rounds':rounds},stop_basis='no_actionable_frontier')
        # Refuse an unavailable retrieval before recording it as the next action.
        # Session/search still enforce the same shared ceiling at dispatch.
        session.add_retrieval()
        resolved = SLOT_PATTERN.sub(lambda m: bindings[m.group(1)]['value'], target['question'])
        query = needs.get(target['id']) or question+'\nInformation needed: '+resolved
        session.event('controller_decision', action='retrieve', target_node=target['id'], query=query,
                      selection_policy='least_targeted_ready_then_downstream_then_id',
                      frontier_attempts={n['id']:retrieval_attempts.get(n['id'],0)
                                         for n in frontier(plan, bindings)},
                      consumed_dependencies={d:bindings[d]['value'] for d in target['dependencies']})
        additions, retrieval = retrieve_round(retriever, query, session, previous=evidence)
        retrieval_attempts[target['id']] = retrieval_attempts.get(target['id'], 0) + 1
        evidence = merge_evidence(evidence, additions)
        if bindings:
            # Conservative invalidation: every earlier answer and all descendants
            # must be rechecked after evidence changes; no stale cached support.
            session.event('cache_invalidated', node_ids=sorted(bindings), reason='evidence_changed_recheck_all')
        bindings = {}
        states = []
        session.event('round_started', evidence_sha256=digest(evidence))
        for node in plan['nodes']:
            nid = node['id']
            missing = [d for d in node['dependencies'] if d not in bindings]
            if missing:
                state=dict(id=nid,status='blocked',question=node['question'],missing_dependencies=missing,answer='',refs=[])
                states.append(state)
                session.event('node_blocked', node_id=nid, question=node['question'],missing_dependencies=missing)
                continue
            inputs = ancestor_bindings(node, by_id, bindings)
            consumed = {d:bindings[d]['value'] for d in node['dependencies']}
            resolved = SLOT_PATTERN.sub(lambda m: bindings[m.group(1)]['value'], node['question'])
            session.event('node_inputs', node_id=nid, template=node['question'], resolved_question=resolved,
                          consumed_dependencies=consumed, input_bindings=inputs)
            with session.phase('node_assessment:'+nid):
                candidate = assess_node(llm,resolved,node['answer_type'],evidence,
                                        original_question=question,bindings=inputs)
            certificate = None
            if candidate['sufficient']:
                refs = list(dict.fromkeys(candidate['refs']+[r for b in inputs.values() for r in b['refs']]))
                with session.phase('node_support:'+nid):
                    certificate = check_support(llm,resolved,candidate['answer'],refs,evidence,inputs,scope='subquestion')
                supported = certificate['supported']
            else:
                refs, supported = [], False
            missing_query = (certificate or {}).get('missing_query') or candidate['missing_query'] or resolved
            needs[nid] = missing_query
            state = dict(id=nid,status='supported' if supported else 'insufficient',question=resolved,
                         answer=candidate['answer'] if supported else '',refs=refs if supported else [],
                         candidate=candidate,certificate=certificate,consumed_dependencies=consumed,
                         missing_query=missing_query)
            states.append(state)
            session.event('node_assessed', **state)
            if supported:
                bindings[nid] = dict(value=candidate['answer'],refs=refs,source_question=node['question'],
                    answer_type=node['answer_type'],consumed_dependencies=consumed,
                    entity=certificate['entity'],property=certificate['property'],
                    evidence_sha256=digest(evidence),certificate=certificate)
        answer = bindings.get(plan['final'],{}).get('value','')
        goal = None
        if answer:
            if len(answer.split()) > 5:
                with session.phase('shorten_root'):
                    answer = llm.shorten_answer(question,evidence,bindings,plan['final'])
            if answer:
                with session.phase('original_goal_support'):
                    goal = check_support(llm,question,answer,bindings[plan['final']]['refs'],evidence,
                                         bindings,scope='original_goal')
        gate = stop_gate(plan,bindings,states,goal)
        rounds.append(dict(nodes=states,bindings=copy.deepcopy(bindings),goal_certificate=goal,
                           stop_gate=gate,retrieval=retrieval,evidence_sha256=digest(evidence)))
        session.event('round_completed', **rounds[-1])
        session.event('stop_gate', **gate)
        if gate['allowed']:
            session.event('controller_decision', action='stop', reason='verified_goal_and_dependency_closure')
            return dict(answer=answer,status='answered',citations_native=bindings[plan['final']]['refs'],
                        evidence_final=evidence,details={'rounds':rounds},stop_basis='active_dependency_and_support_gate')
        if plan['final'] in bindings:
            bindings.pop(plan['final'])
            needs[plan['final']] = (goal or {}).get('missing_query') or question
        session.event('stop_blocked', unresolved=gate['unresolved_nodes'],
                      reason='original_goal_or_dependency_support_missing')
        # The next retrieve_round is gated by the same shared Session budget;
        # budget exhaustion is never relabelled as a successful stop.


METHODS = {'standard':standard,'max4':max4,'operadic':operadic}
