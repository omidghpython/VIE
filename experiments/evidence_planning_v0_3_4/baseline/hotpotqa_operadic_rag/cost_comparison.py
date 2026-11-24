"""Whole-method token comparisons, including failed/retried calls. No inference."""
from collections import Counter


def _tokens(row, prefix):
    values = [int(row[prefix + '_cumulative_' + kind + '_tokens'])
              for kind in ('prompt', 'completion')]
    if min(values) < 0:
        raise ValueError('Token counts cannot be negative.')
    return sum(values)


def paired_token_report(rows):
    """Compare A and B in the SAME full-run CSV, never B against the OC subset."""
    if not rows or len({r['question_id'] for r in rows}) != len(rows):
        raise ValueError('A paired token report requires distinct, nonempty question rows.')
    totals = {p: sum(_tokens(r, p) for r in rows) for p in ('std', 'operadic', 'oc')}
    missing = {p: sum(r[p + '_status'] != 'completed' for r in rows) for p in ('std', 'operadic')}
    answered = {p: sum(r[p + '_status'] == 'completed' and bool(str(r[key]).strip()) for r in rows)
                for p, key in (('std', 'answer_std'), ('operadic', 'answer_decomposed'))}
    # Failed/pending rows stay in both the token totals and the denominator.
    # Cheap early failures are never certified as successful token savings.
    less = totals['operadic'] < totals['std']
    if missing['std'] or missing['operadic']:
        status = 'not_established_incomplete_run' if less else 'fails_strict_token_condition'
    elif not less:
        status = 'fails_strict_token_condition'
    elif answered['operadic'] < answered['std']:
        status = 'not_established_reduced_answer_coverage'
    else:
        status = 'meets_token_condition_quality_requires_review'
    return {'criterion': 'B total input + output tokens < A total input + output tokens on all same questions',
            'requested': len(rows), 'standard_tokens': totals['std'], 'decomposed_tokens': totals['operadic'],
            'decomposed_minus_standard': totals['operadic'] - totals['std'],
            'decomposed_to_standard_ratio': totals['operadic'] / totals['std'] if totals['std'] else None,
            'observed_total_strictly_lower': less, 'status': status,
            'incomplete_or_failed': missing, 'nonempty_completed': answered,
            'per_question_cost': dict(Counter('less' if _tokens(r, 'operadic') < _tokens(r, 'std') else
                                              'equal' if _tokens(r, 'operadic') == _tokens(r, 'std') else 'more'
                                              for r in rows)),
            'oc_diagnostic_extra_tokens': totals['oc'], 'all_experiment_tokens': sum(totals.values()),
            'scope': 'Includes generation, judging, repair, evidence checks, node/final answers and retries. '
                     'OC is an extra evaluation call, not Standard RAG; it is shown separately. '
                     'A lower token count alone does not establish answer quality.'}


def pilot_token_report(samples, settings, total_tokens, reference, incomplete):
    """A pilot is only a lower bound on B; it can NEVER establish full savings."""
    result = {'criterion': 'Whole decomposed RAG must use strictly fewer input + output tokens than Standard RAG',
              'pilot_tokens': total_tokens, 'full_decomposed_tokens': None,
              'full_token_condition_met': None,
              'status': 'not_comparable',
              'note': 'Historical A reference only. Pilot omits retrieval/answering and semantic repair. '
                      'Being below A here is necessary, not sufficient; use a full paired run to decide. '
                      'No questions, evidence or failed attempts are removed to reduce reported cost.'}
    if not reference:
        return result
    expected = [(s['question_id'], s['question'], s['type']) for s in samples]
    actual = [(r['question_id'], r['question'], r['type']) for r in reference['questions']]
    if expected != actual:
        return result
    for field in ('model', 'model_revision', 'use_4bit'):
        if settings[field] != reference['settings'][field]:
            return result
    direct = sum(r['input_tokens'] + r['output_tokens'] for r in reference['questions'])
    result.update(standard_reference_tokens=direct,
                  standard_reference_status=dict(Counter(r['status'] for r in reference['questions'])),
                  reference_source=reference['source'],
                  remaining_tokens_below_historical_standard=direct - total_tokens - 1)
    if settings['backend'] != 'LocalQwen':
        result['status'] = 'not_measured_scripted_backend'
    elif total_tokens >= direct:
        result['status'] = 'pilot_already_exceeds_or_equals_historical_standard'
    elif incomplete:
        result['status'] = 'pilot_incomplete_full_savings_not_established'
    else:
        result['status'] = 'pilot_below_reference_full_savings_not_established'
    return result
