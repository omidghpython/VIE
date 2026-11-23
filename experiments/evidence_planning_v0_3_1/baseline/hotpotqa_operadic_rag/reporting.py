"""Compare methods on answer quality, fact coverage, stopping, calls and time."""
from pathlib import Path
import json
import pandas as pd
from .cost_comparison import paired_token_report


def mean(values):
    values = pd.to_numeric(values, errors='coerce').dropna()
    return float(values.mean()) if len(values) else None


def method_summary(df, label, prefix):
    done = df[df[prefix + '_status'] == 'completed']
    return {'Method': label, 'Requested': len(df), 'Completed': len(done),
            'Abstained completed': int((done['answer_decomposed' if prefix == 'operadic' else 'answer_std'].fillna('').str.strip() == '').sum()),
            'Failed': int(df[prefix + '_status'].isin(['failed','interrupted']).sum()),
            'Pending': int((df[prefix + '_status'] == 'pending').sum()),
            'Accuracy completed (F1>=0.5)': mean(done[prefix + '_acc']),
            'Accuracy all requested': float(pd.to_numeric(df[prefix + '_acc'], errors='coerce').fillna(0).sum() / len(df)),
            'Token-F1 completed': mean(done[prefix + '_f1']), 'EM completed': mean(done[prefix + '_em']),
            'Support coverage first': mean(done[prefix + '_supporting_fact_coverage_first']),
            'Support coverage final': mean(done[prefix + '_supporting_fact_coverage_final']),
            'Premature stopping rate completed': mean(done[prefix + '_premature_stopping']),
            'Mean retrieval calls completed': mean(done[prefix + '_retrieval_steps']),
            'Mean core time completed (s)': mean(done[prefix + '_execution_time_sec']),
            'Cumulative retrieval calls incl retries': int(df[prefix + '_cumulative_retrieval_steps'].sum()),
            'Cumulative LLM calls incl retries': int(df[prefix + '_cumulative_llm_calls'].sum()),
            'Cumulative input tokens incl retries': int(df[prefix + '_cumulative_prompt_tokens'].sum()),
            'Cumulative output tokens incl retries': int(df[prefix + '_cumulative_completion_tokens'].sum()),
            'Cumulative time incl retries (s)': float(df[prefix + '_cumulative_execution_time_sec'].sum())}


def print_summary(df, output_csv):
    if df.empty:
        return
    summary_rows = []
    for scope, subset in [('all', df)] + [(kind, df[df['question_type'] == kind]) for kind in sorted(df['question_type'].unique())]:
        for label, prefix in [('A: Standard RAG','std'), ('B: Typed-tree RAG','operadic')]:
            summary_rows.append({'Question type': scope, **method_summary(subset, label, prefix)})
    summary = pd.DataFrame(summary_rows)
    print('\nMethod comparison (failed runs are separate from premature stopping):')
    print(summary.to_string(index=False))
    oc_done = df[df['oc_status'] == 'completed']
    print('\nMean OC for nonempty answer pairs:', mean(oc_done['oc_score']))
    print('OC >= 0.5 rate for valid pairs:', mean(oc_done['oc_consistent']))
    print('Mean B core time (s):', mean(df.loc[df['operadic_status'] == 'completed','operadic_core_time_sec']))
    print('Mean B additional direct-answer/OC time (s):', mean(oc_done['operadic_oc_time_sec']))
    print('Mean B total time for fully completed B phases (s):', mean(df.loc[(df['operadic_status'] == 'completed') & (df['oc_status'] == 'completed'),'operadic_total_time_sec']))
    print('Supporting-fact coverage measures retrieved full sentences, not whether the model used them correctly.')
    print('CSV:', Path(output_csv).resolve())
    # Persist the comparison rather than leaving it only on the console.
    summary.to_csv(Path(output_csv).with_suffix('.summary.csv'), index=False, encoding='utf-8-sig')
    tokens = paired_token_report(df.fillna('').to_dict('records'))
    print('\nWhole-method token condition:', json.dumps(tokens, ensure_ascii=False))
    Path(output_csv).with_suffix('.token_comparison.json').write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
