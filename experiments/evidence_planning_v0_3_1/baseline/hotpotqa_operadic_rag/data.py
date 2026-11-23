"""Balanced native HotpotQA types; exactly ten local passages per question."""
import random
import re
import json
from pathlib import Path
from typing import Any, Dict, List

from .config import DATASET_NAME, DATASET_CONFIG, DATASET_SPLIT, RANDOM_SEED


def context_passages(context: Any) -> List[Dict]:
    if isinstance(context, dict):
        titles, sentences = context.get('title'), context.get('sentences')
        if not isinstance(titles, list) or not isinstance(sentences, list) or len(titles) != len(sentences):
            raise ValueError('Invalid HotpotQA context columns.')
        pairs = list(zip(titles, sentences))
    elif isinstance(context, list):
        pairs = context
    else:
        raise ValueError('Invalid HotpotQA context.')
    if len(pairs) != 10:
        raise ValueError(f'Each question must have exactly 10 context paragraphs, found {len(pairs)}.')
    passages = []
    for index, pair in enumerate(pairs):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('Each context paragraph needs a title and sentences.')
        title, sentences = pair
        if not isinstance(title, str) or not title.strip() or not isinstance(sentences, list) or not sentences:
            raise ValueError('Invalid context title or sentence list.')
        if not all(isinstance(sentence, str) for sentence in sentences):
            raise ValueError('Context sentences must be strings.')
        # Sentence numbering and titles must remain exact for evaluation.
        passages.append({'index': index, 'title': title, 'sentences': list(sentences),
                         'sentence_ids': list(range(len(sentences))),
                         'text': f'Title: {title}\nPassage: ' + ' '.join(sentences)})
    return passages


def make_passage_corpus(sample: Dict) -> List[Dict]:
    """Only one question's ten contexts; never pool or deduplicate questions."""
    return context_passages(sample['context'])


def select_balanced(rows, n_samples=40, seed=RANDOM_SEED):
    if type(n_samples) is not int or not 30 <= n_samples <= 50 or n_samples % 2:
        raise ValueError('--n-samples must be an even number from 30 to 50.')
    pools = {'bridge': [], 'comparison': []}
    seen = set()
    for item in rows:
        row = dict(item)
        kind = row.get('type')
        if kind not in pools:
            continue
        qid = row.get('id', row.get('_id'))
        if not isinstance(qid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', qid) or qid in seen:
            raise ValueError('Missing, duplicate or unsafe original HotpotQA ID.')
        seen.add(qid)
        row['question_id'] = qid
        pools[kind].append(row)
    selected = []
    for kind, pool in pools.items():
        pool.sort(key=lambda row: row['question_id'])
        random.Random(seed).shuffle(pool)
        if len(pool) < n_samples // 2:
            raise ValueError(f'Not enough {kind} questions.')
        selected.extend(pool[:n_samples // 2])
    random.Random(seed).shuffle(selected)
    for row in selected:
        if not isinstance(row.get('question'), str) or not row['question'].strip():
            raise ValueError('Question text is missing.')
        make_passage_corpus(row)  # Validate exact local scope before loading models.
    return selected


def load_hotpotqa(n_samples: int) -> List[Dict]:
    from datasets import load_dataset
    dataset = load_dataset(DATASET_NAME, DATASET_CONFIG, split=DATASET_SPLIT)
    return select_balanced(dataset, n_samples)


def load_sample_snapshot(path, n_samples):
    """Reuse the exact original sample order/contexts, without downloading/shuffling."""
    from .checkpoint import digest
    path = Path(path)
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or len(rows) != n_samples:
        raise ValueError('Sample snapshot count differs from --n-samples.')
    manifest_path = path.with_name('manifest.json')
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('samples_sha256') != digest(rows):
            raise ValueError('Sample snapshot does not match its manifest checksum.')
        if manifest.get('question_ids') != [r.get('question_id') for r in rows]:
            raise ValueError('Snapshot IDs/order differ from the baseline manifest.')
    ids = set()
    for row in rows:
        qid = row.get('question_id')
        if (not isinstance(qid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,100}', qid)
                or qid in ids or qid != row.get('id', row.get('_id'))
                or not isinstance(row.get('question'), str) or not row['question'].strip()
                or row.get('type') not in ('bridge', 'comparison')):
            raise ValueError('Invalid sample identity, type or question in snapshot.')
        ids.add(qid)
        make_passage_corpus(row)
    if sum(r['type'] == 'bridge' for r in rows) != n_samples // 2:
        raise ValueError('Snapshot must retain the balanced bridge/comparison cohort.')
    return rows
