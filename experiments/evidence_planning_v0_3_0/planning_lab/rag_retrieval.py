"""Real question-local retrieval, shared by every method; no reference labels."""
from collections import Counter
import math
import re
import importlib.metadata
from .common import digest


def passages_from_states(states):
    sentences = {}
    for state in states:
        for item in state['evidence']:
            if item['ref'] in sentences and sentences[item['ref']] != item:
                raise ValueError('Evidence identity differs across snapshots')
            sentences[item['ref']] = item
    groups = {}
    for ref, item in sentences.items():
        match = re.fullmatch(r'p(\d+):s(\d+)', ref)
        if not match or int(match[2]) != item['sentence_id']:
            raise ValueError('Invalid original sentence ID')
        groups.setdefault(int(match[1]), []).append(item)
    if set(groups) != set(range(10)):
        raise ValueError('Exactly ten question-local documents are required')
    result = []
    for index, rows in sorted(groups.items()):
        rows.sort(key=lambda r: r['sentence_id'])
        if [r['sentence_id'] for r in rows] != list(range(len(rows))) or len({r['title'] for r in rows}) != 1:
            raise ValueError('Incomplete or inconsistent document')
        text = [r['text'] for r in rows]
        result.append(dict(index=index, title=rows[0]['title'], sentences=text,
                           sentence_ids=list(range(len(rows))),
                           text='Title: '+rows[0]['title']+'\nPassage: '+' '.join(text)))
    return result


class BM25Retriever:
    """Deterministic lexical backend for CPU checks or an explicitly frozen study."""
    def __init__(self, passages):
        self.passages = passages
        self.tokens = [Counter(re.findall(r'\w+', p['text'].casefold())) for p in passages]
        self.lengths = [sum(c.values()) for c in self.tokens]
        self.mean = sum(self.lengths)/len(self.lengths) or 1
        self.df = Counter(token for row in self.tokens for token in row)

    def search(self, query, top_k=3, exclude_indices=()):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Empty retrieval query')
        terms = set(re.findall(r'\w+', query.casefold()))
        n = len(self.passages)
        ranked = []
        for i, row in enumerate(self.tokens):
            if self.passages[i]['index'] in exclude_indices:
                continue
            score = sum(math.log(1+(n-self.df[t]+.5)/(self.df[t]+.5))*row[t]*2.5 /
                        (row[t]+1.5*(.25+.75*self.lengths[i]/self.mean)) for t in terms if row[t])
            ranked.append(dict(self.passages[i], bm25_score=score))
        return sorted(ranked, key=lambda p: (-p['bm25_score'], p['index']))[:top_k]


class RetrieverFactory:
    def __init__(self, config):
        self.config, self.encoder = config, None
        self.identity = dict(backend=config['retriever'], top_k=3,
                             embedding_model=None, embedding_revision=None,
                             packages={'numpy':importlib.metadata.version('numpy')})
        if config['retriever'] == 'hybrid':
            from sentence_transformers import SentenceTransformer
            from hotpotqa_operadic_rag.config import EMBEDDING_MODEL, EMBEDDING_REVISION
            self.encoder = SentenceTransformer(EMBEDDING_MODEL, revision=EMBEDDING_REVISION,
                local_files_only=not config['allow_model_download'], device='cpu')
            self.identity.update(embedding_model=EMBEDDING_MODEL, embedding_revision=EMBEDDING_REVISION,
                                 hybrid_alpha=.6, embedding_device='cpu')
            self.identity['packages'].update({name:importlib.metadata.version(name)
                for name in ['sentence-transformers','rank-bm25']})
        self.cache = {}

    def __call__(self, passages):
        key = digest(passages)
        if key not in self.cache:
            if self.encoder is None:
                self.cache[key] = BM25Retriever(passages)
            else:
                from hotpotqa_operadic_rag.retriever import HybridRetriever
                self.cache[key] = HybridRetriever(passages, encoder=self.encoder)
        return self.cache[key]
