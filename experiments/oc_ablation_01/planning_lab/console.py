"""Read-only console notifications; never decide a research action or change a journal."""
import copy
import logging
from pathlib import Path
import platform
import sys


def notify(observer, kind, **fields):
    if observer is None:
        return
    try:
        # Display callbacks must not mutate plans, decisions, or measured usage.
        observer(kind, **copy.deepcopy(fields))
    except Exception:
        # A broken console/file handler must not invalidate a saved model result.
        pass


def text(value, limit=300):
    value = str(value).replace('\r', ' ').replace('\n', ' ')
    value = ''.join(c if c >= ' ' else ' ' for c in value)
    return value if len(value) <= limit else value[:limit] + ' ... [display shortened]'


def number(value):
    return 'unknown' if value is None else str(value)


class ConsoleProgress:
    """The accepted max4 timestamp/level format, extended to the three-method runner."""
    def __init__(self, output=None, stream=None):
        self.logger = logging.Logger('hotpotqa.console', level=logging.INFO)
        self.logger.propagate = False
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.log_path = None
        if output is not None:
            try:
                path = Path(output) / 'console.log'
                path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(path, mode='a', encoding='utf-8')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.log_path = path
            except OSError:
                notify(self, 'setup', message='Console file unavailable; terminal display remains enabled.')

    def close(self):
        for handler in self.logger.handlers[:]:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
            self.logger.removeHandler(handler)

    def __call__(self, kind, **data):
        info = self.logger.info
        if kind == 'startup':
            info('HotpotQA Evidence Planning %s | baseline v3.2.4-max4', data['version'])
            info('Python: %s | %s', platform.python_version(), sys.executable)
            info('Methods: dependent / independent | split: %s | questions: %s', data['role'], data['questions'])
            config = data['config']
            info('Shared budget per question/method: LLM=%s | tokens=%s | retrieval=%s | top_k=%s',
                 config['max_llm_calls'], config['max_total_tokens'], config['max_retrieval_calls'], config['top_k'])
            info('Session cap: %s new questions | Output: %s',
                 data['cap'] if data['cap'] is not None else 'all remaining', Path(data['output']).resolve())
        elif kind == 'setup':
            info('[SETUP] %s', data['message'])
        elif kind == 'runtime_ready':
            identity = data['identity']
            info('PyTorch: %s | CUDA: %s | GPU: %s', identity.get('packages', {}).get('torch', 'unknown'),
                 identity.get('cuda', 'unknown'), identity.get('gpu', 'unknown'))
            info('Model: %s | quantization: %s | load: %.2fs', identity.get('model', 'unknown'),
                 identity.get('quantization', 'unknown'), data['seconds'])
        elif kind == 'question_started':
            info('[%s/%s] %s (%s) | methods pending: %s', data['index'], data['total'], data['qid'],
                 data['question_type'], ', '.join(data['pending']))
            info('Question: %s', text(data['question'], 2000))
        elif kind == 'question_skipped':
            info('[%s/%s] %s | SKIP: all paired method records already exist', data['index'], data['total'], data['qid'])
        elif kind == 'plan_ready':
            plan = data['plan'] or {}
            info('[PLAN] %s | %s | historical/shared budget debit: calls=%s tokens=%s',
                 data['status'], data['origin'], data['debit']['llm_calls'], number(data['debit']['total_tokens']))
            for node in plan.get('nodes', []):
                info('  %s <- %s | %s', node['id'], ','.join(node['dependencies']) or '(none)', text(node['question']))
        elif kind == 'method_started':
            info('--- %s: START ---', data['method'])
        elif kind == 'retriever_ready':
            setup = data['setup']
            if setup['status'] == 'failed':
                self.logger.error('[SETUP] %s | failure records will be saved; later questions continue', text(setup['error']))
            else:
                info('[SETUP] Question-local index ready')
        elif kind == 'phase_started':
            info('[PHASE] %s', data['stage'])
        elif kind in {'llm_started', 'llm_completed', 'llm_replayed', 'llm_failed'}:
            prefix = f"[LLM {data['call']}] {data['stage']}"
            if kind == 'llm_started':
                info('%s | running | input=%s | max_output=%s', prefix, data['input_tokens'], data['maximum'])
            elif kind == 'llm_completed':
                info('%s | %s | input=%s output=%s | seconds=%s', prefix, data['status'],
                     data['input_tokens'], number(data['output_tokens']), number(data['seconds']))
            elif kind == 'llm_replayed':
                info('%s | REPLAY saved call; no new generation | status=%s', prefix, data['status'])
            else:
                self.logger.error('%s | failed; usage unknown | %s', prefix, text(data['error']))
        elif kind == 'retrieval_started':
            info('[RETRIEVAL %s] %s | query: %s', data['call'], 'REPLAY saved search' if data['replay'] else 'running', text(data['query']))
        elif kind == 'retrieval_executed':
            info('[RETRIEVAL] evidence passage IDs: %s', data['new_indices'])
        elif kind == 'controller_decision':
            info('[DECISION] %s | target=%s | %s', data['action'], data.get('target_node', '-'), text(data.get('reason', data.get('query', ''))))
        elif kind == 'node_inputs':
            info('[NODE %s] inputs=%s | %s', data['node_id'], data['consumed_dependencies'], text(data['resolved_question']))
        elif kind == 'node_assessed':
            info('[NODE %s] %s (model assessment) | answer=%s | refs=%s', data['id'], data['status'],
                 text(data['answer']) or '(none)', data['refs'])
        elif kind == 'node_blocked':
            info('[NODE %s] BLOCKED | missing prerequisites: %s', data['node_id'], data['missing_dependencies'])
        elif kind == 'cache_invalidated':
            info('[CACHE] Recheck previous bindings after evidence change: %s', data['node_ids'])
        elif kind == 'stop_gate':
            info('[STOP GATE] allowed=%s | unresolved=%s | invalid inputs=%s', data['allowed'],
                 data['unresolved_nodes'], data['stale_or_missing_input_bindings'])
        elif kind == 'method_completed':
            result, method = data['result'], data['method']
            costs = result['costs']
            info('--- %s: %s | answer: %s ---', method, result['status'], text(result['answer']) or '(none)')
            info('%s cost: actual LLM=%s | retrieval=%s | tokens=%s | charged tokens incl. plan=%s | wall=%s s',
                 method, costs['llm_calls'], costs['retrieval_calls'], number(costs['total_tokens']),
                 number(costs['charged_total_tokens']), number(result['execution_seconds']))
            if result.get('error'):
                self.logger.warning('%s: %s', method, text(result['error']))
        elif kind == 'run_completed':
            summary = data['summary']
            info('%s | saved method records: %s/%s', 'RUN COMPLETE' if summary['execution_complete'] else 'SESSION PAUSED',
                 summary['recorded_trials'], summary['expected_trials'])
            info('Recorded physical usage: LLM=%s | retrieval=%s | tokens=%s', summary['actual_llm_calls'],
                 summary['actual_retrieval_calls'], number(summary['actual_total_tokens']))
            info('Saved answers/statuses are not independent semantic validation.')
            info('Completion counts stored records, including failures.')
        elif kind == 'report_ready':
            info('Report: %s', Path(data['output']).resolve() / 'RAG_REPORT_FA.txt')
            info('Detailed records: %s', Path(data['output']).resolve())
            info('Console log: %s', self.log_path)
        elif kind == 'interrupted':
            self.logger.warning('Interrupted. Saved records are preserved. In-flight calls are not silently retried.')
        elif kind == 'failed':
            self.logger.error('Run blocked: %s. Saved records are preserved.', text(data['error'], 1000))
