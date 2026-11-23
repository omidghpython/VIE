"""Shared budgets and durable call journals for all three RAG methods."""
from contextlib import contextmanager
from pathlib import Path
import time
from .common import atomic_json, digest, read_json
from hotpotqa_operadic_rag.llm import LocalQwen


class BudgetExceeded(RuntimeError):
    pass


class UnknownUsage(RuntimeError):
    pass


class Session:
    def __init__(self, backend, retriever, config, output, plan_debit=None):
        self.backend, self.retriever, self.config = backend, retriever, config
        self.output = Path(output)
        self.debit = plan_debit or {'llm_calls': 0, 'total_tokens': 0}
        self.calls, self.searches, self.events = [], [], []
        self.stage = 'baseline'
        self.evidence = []

    @contextmanager
    def phase(self, stage):
        previous = self.stage
        self.stage = stage
        try:
            yield
        finally:
            self.stage = previous

    def event(self, kind, **fields):
        self.events.append(dict(kind=kind, **fields))

    def used_tokens(self):
        if any(r.get('completion_tokens') is None for r in self.calls):
            raise UnknownUsage('A model call has unknown output usage; no further calls are allowed.')
        return self.debit['total_tokens'] + sum(r['prompt_tokens'] + r['completion_tokens'] for r in self.calls)

    def generate(self, messages, maximum):
        length = self.backend.count_tokens(messages)
        if length > self.config['max_input_tokens']:
            raise BudgetExceeded('input_tokens')
        self.backend.check_context(length, maximum)
        if self.debit['llm_calls'] + len(self.calls) >= self.config['max_llm_calls']:
            raise BudgetExceeded('llm_calls')
        if self.used_tokens() + length + maximum > self.config['max_total_tokens']:
            raise BudgetExceeded('total_tokens_reserved_output')
        request = dict(messages=messages, maximum=maximum, seed=self.config['seed'], stage=self.stage)
        path = self.output / 'model_calls' / f'{len(self.calls):03}.json'
        if path.exists():
            row = read_json(path)
            if row['request_sha256'] != digest(request):
                raise ValueError('Model replay request changed; resume refused.')
            self.calls.append(row)
            if row['status'] in {'inflight', 'usage_unknown'}:
                raise UnknownUsage('Interrupted model call; automatic retry is forbidden.')
        else:
            row = dict(request=request, request_sha256=digest(request), status='inflight',
                       prompt_tokens=length, completion_tokens=None, generation_seconds=None, raw=None)
            atomic_json(path, row)
            self.calls.append(row)
            try:
                response = self.backend.generate(messages, maximum, self.config['seed'])
                row.update(raw=response.text, prompt_tokens=response.prompt_tokens,
                           completion_tokens=response.completion_tokens, generation_seconds=response.generation_seconds,
                           status='output_limit' if response.output_limit else 'completed')
                if response.prompt_tokens != length or not 0 <= response.completion_tokens <= maximum:
                    row['status'] = 'invalid_backend_accounting'
                atomic_json(path, row)
            except BaseException as exc:
                row.update(status='usage_unknown', error=f'{type(exc).__name__}: {exc}')
                atomic_json(path, row)
                raise
        if row['status'] != 'completed':
            raise RuntimeError('Recorded model call failed: ' + row['status'])
        return row['raw']

    def add_retrieval(self):
        # Baseline retrieve_round calls this before search; search records usage.
        if len(self.searches) >= self.config['max_retrieval_calls']:
            raise BudgetExceeded('retrieval_calls')

    def search(self, query, top_k, exclude_indices=()):
        self.add_retrieval()
        request = dict(query=query, top_k=top_k, exclude_indices=list(exclude_indices))
        self.event('retrieve_decision', **request)
        path = self.output / 'retrieval_calls' / f'{len(self.searches):03}.json'
        if path.exists():
            row = read_json(path)
            if row['request_sha256'] != digest(request):
                raise ValueError('Retrieval replay request changed.')
            if row['status'] != 'completed':
                self.searches.append(row)
                raise UnknownUsage('Interrupted retrieval; automatic retry is forbidden.')
        else:
            row = dict(request=request, request_sha256=digest(request), status='inflight', seconds=None)
            atomic_json(path, row)
            started = time.perf_counter()
            try:
                hits = self.retriever.search(query, top_k=top_k, exclude_indices=exclude_indices)
                row.update(status='completed', hits=hits, seconds=time.perf_counter()-started)
                atomic_json(path, row)
            except BaseException as exc:
                row.update(status='failed', error=f'{type(exc).__name__}: {exc}', seconds=time.perf_counter()-started)
                atomic_json(path, row)
                self.searches.append(row)
                raise
        self.searches.append(row)
        self.event('retrieval_executed', query=query, new_indices=[p['index'] for p in row['hits'][:3]])
        # Baseline asks for the entire ranking, then consumes the first three.
        by_id = {p['index']: p for p in self.evidence}
        for passage in row['hits'][:3]:
            by_id[passage['index']] = passage
        self.evidence = list(by_id.values())
        return row['hits']

    def costs(self):
        unknown = any(r['completion_tokens'] is None for r in self.calls)
        known = sum(r['prompt_tokens'] + (r['completion_tokens'] or 0) for r in self.calls)
        return dict(llm_calls=len(self.calls), retrieval_calls=len(self.searches),
                    prompt_tokens=sum(r['prompt_tokens'] for r in self.calls),
                    completion_tokens=None if unknown else sum(r['completion_tokens'] for r in self.calls),
                    total_tokens=None if unknown else known, known_tokens=known,
                    unknown_usage=unknown, shared_plan_debit=self.debit,
                    charged_llm_calls=self.debit['llm_calls']+len(self.calls),
                    charged_total_tokens=None if unknown else self.debit['total_tokens']+known,
                    generation_seconds=None if any(r['generation_seconds'] is None for r in self.calls)
                    else sum(r['generation_seconds'] for r in self.calls),
                    retrieval_seconds=None if any(r['seconds'] is None for r in self.searches)
                    else sum(r['seconds'] for r in self.searches))


class TrackedRetriever:
    def __init__(self, session):
        self.session = session
        self.passages = session.retriever.passages

    def search(self, query, top_k, exclude_indices=()):
        return self.session.search(query, top_k, exclude_indices)


class BudgetedQwen(LocalQwen):
    """Reuse original answer/JSON prompts; route every generation through Session."""
    def __init__(self, session):
        self.session = session
        self.intermediate_tokens = session.config['intermediate_tokens']
        self.max_new_tokens = session.config['answer_tokens']
        self.plan_tokens = 3072

    def generate(self, messages, max_new_tokens=None):
        return self.session.generate(messages, self.max_new_tokens if max_new_tokens is None else max_new_tokens)
