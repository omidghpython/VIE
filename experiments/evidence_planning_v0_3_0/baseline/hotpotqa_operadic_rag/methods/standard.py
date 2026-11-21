"""Standard RAG: retain first three passages and append three new ones if needed."""
from ..retriever import retrieve_round, merge_evidence
from .common import standard_sufficiency_check


def run_standard_rag(question, retriever, llm, tracker):
    first, trace1 = retrieve_round(retriever, question, tracker)
    check = standard_sufficiency_check(llm, question, first)
    second, retrieval_trace = [], [trace1]
    if not check['is_sufficient']:
        second, trace2 = retrieve_round(retriever, check['follow_up_query'], tracker, previous=first)
        retrieval_trace.append(trace2)
    evidence = merge_evidence(first, second)
    answer = llm.answer(question, evidence)
    return {'answer_std': answer, 'std_is_sufficient': check['is_sufficient'],
            'std_follow_up_query': check['follow_up_query'],
            'stopped_after_first': check['is_sufficient'], 'evidence_first': first,
            'evidence_final': evidence, 'retrieval_trace': retrieval_trace}
