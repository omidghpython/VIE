"""Question-local hybrid ranking: ten candidates first, seven unseen candidates second."""
import re
import numpy as np

from .config import EMBEDDING_MODEL, EMBEDDING_REVISION, HYBRID_ALPHA, TOP_K
from .data import make_passage_corpus
from .utils import safe_minmax, clear_cuda_cache


def bm25_tokens(text):
    return re.findall(r'\b\w+\b', text.casefold())


class HybridRetriever:
    def __init__(self, passages, alpha=HYBRID_ALPHA, encoder=None):
        from rank_bm25 import BM25Okapi
        if len(passages) != 10:
            raise ValueError('A retriever must contain exactly one question\'s 10 passages.')
        if not 0 <= alpha <= 1:
            raise ValueError('alpha must be in [0,1].')
        self.passages, self.alpha = list(passages), alpha
        owned_encoder = encoder is None
        if owned_encoder:
            import torch
            from sentence_transformers import SentenceTransformer
            encoder = SentenceTransformer(EMBEDDING_MODEL, revision=EMBEDDING_REVISION, device='cuda' if torch.cuda.is_available() else 'cpu')
        self.encoder = encoder
        texts = [p['text'] for p in self.passages]
        self.embeddings = encoder.encode(texts, convert_to_numpy=True, normalize_embeddings=True,
                                         show_progress_bar=False, batch_size=32).astype(np.float32)
        self.bm25 = BM25Okapi([bm25_tokens(text) for text in texts])
        if owned_encoder:
            encoder.to('cpu')
            clear_cuda_cache()

    def search(self, query, top_k=TOP_K, exclude_indices=()):
        """Exclude prior hits before normalization and ranking of eligible candidates."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError('A nonempty query is required.')
        excluded = set(exclude_indices)
        all_indices = set(range(len(self.passages)))
        if not excluded <= all_indices:
            raise ValueError('Excluded passage indices are outside this question context.')
        candidates = [i for i in range(len(self.passages)) if i not in excluded]
        if not candidates:
            return []
        vector = self.encoder.encode([query], convert_to_numpy=True, normalize_embeddings=True,
                                     show_progress_bar=False)[0].astype(np.float32)
        dense = self.embeddings[candidates] @ vector
        # BM25's document statistics stay tied to this question's ten contexts.
        # Only eligible candidates enter normalization and the hybrid ranking.
        sparse = np.asarray(self.bm25.get_scores(bm25_tokens(query)), dtype=np.float64)[candidates]
        dense_norm, sparse_norm = safe_minmax(dense), safe_minmax(sparse)
        scores = self.alpha * dense_norm + (1 - self.alpha) * sparse_norm
        ranked = np.argsort(-scores, kind='stable')[:max(0, int(top_k))]
        return [dict(self.passages[candidates[int(i)]], dense_score=float(dense[i]),
                     bm25_score=float(sparse[i]), hybrid_score=float(scores[i])) for i in ranked]


def build_question_retrievers(samples):
    """Share the encoder, not the searchable corpus. Offload before loading Qwen."""
    import torch
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer(EMBEDDING_MODEL, revision=EMBEDDING_REVISION, device='cuda' if torch.cuda.is_available() else 'cpu')
    try:
        result = {sample['question_id']: HybridRetriever(make_passage_corpus(sample), encoder=encoder)
                  for sample in samples}
    finally:
        encoder.to('cpu')
        clear_cuda_cache()
    return result


def retrieve_round(retriever, query, tracker, previous=()):
    """One search: best three of ten first, then best three of seven remaining.

    Previous passages are excluded from second-round candidates but are retained
    in accumulated evidence by the caller. No post-ranking deduplication shortcut.
    """
    tracker.add_retrieval()
    previous_ids = get_indices(previous)
    if len(previous_ids) not in (0, TOP_K) or len(set(previous_ids)) != len(previous_ids):
        raise ValueError('A round must retain either zero or exactly three distinct previous passages.')
    candidates = [p['index'] for p in retriever.passages if p['index'] not in previous_ids]
    ranked = retriever.search(query, top_k=len(candidates), exclude_indices=previous_ids)
    additions = ranked[:TOP_K]
    if (len(additions) != TOP_K or len(set(get_indices(additions))) != TOP_K
            or set(get_indices(additions)) & set(previous_ids)):
        raise ValueError('Retrieval did not provide three distinct new passages.')
    return additions, {'query': query, 'ranked_indices': get_indices(ranked),
                       'candidate_indices': candidates, 'excluded_indices': previous_ids,
                       'new_indices': get_indices(additions), 'retained_indices': get_indices(previous)}


def format_evidence(evidence):
    if not evidence:
        return '(No evidence retrieved.)'
    if any(len(p['sentence_ids']) != len(p['sentences']) for p in evidence):
        raise ValueError('Evidence sentence IDs/text differ in length; no sentence was truncated.')
    # Stable source IDs survive reordering and the second retrieval. Every original
    # sentence is included verbatim; only the duplicated title/Passage wrapper goes.
    return '\n\n'.join(
        f"[Evidence {item['index']} | Title: {item['title']}]\n" +
        '\n'.join(f"[{item['index']}:{sid}] {sentence}"
                  for sid, sentence in zip(item['sentence_ids'], item['sentences']))
        for item in evidence)


def get_indices(evidence):
    return [int(p['index']) for p in evidence]


def merge_evidence(*groups):
    merged, seen = [], set()
    for group in groups:
        for passage in group:
            if passage['index'] not in seen:
                merged.append(passage)
                seen.add(passage['index'])
    return merged
