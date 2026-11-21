"""SQuAD-compatible normalization, F1, EM and threshold accuracy."""
import re
import string
from collections import Counter
from typing import Any, Dict

from .utils import to_text

_ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)

def normalize_answer(text: Any) -> str:
    value = str(text or "").lower()
    value = value.translate(str.maketrans("", "", string.punctuation))
    value = _ARTICLES.sub(" ", value)
    return " ".join(value.split())

def squad_em(prediction: Any, reference: Any) -> float:
    return float(normalize_answer(prediction) == normalize_answer(reference))

def squad_f1(prediction: Any, reference: Any) -> float:
    pred = normalize_answer(prediction).split()
    gold = normalize_answer(reference).split()
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    overlap = sum((Counter(pred) & Counter(gold)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(gold)
    return 2 * precision * recall / (precision + recall)

def add_metrics(row: Dict[str, Any], gold: str) -> Dict[str, Any]:
    pairs = [
        ("std", "answer_std"),
        ("decomposed", "answer_decomposed"),
        ("direct", "answer_direct"),
    ]
    for prefix, answer_key in pairs:
        f1 = squad_f1(row.get(answer_key, ""), gold)
        em = squad_em(row.get(answer_key, ""), gold)
        row[f"{prefix}_f1"] = f1
        row[f"{prefix}_em"] = em
        row[f"{prefix}_acc"] = float(f1 >= 0.5)
    return row

def reference_answer(row: Dict[str, Any]) -> str:
    return to_text(row.get("answer"), "")


def supporting_facts_set(value):
    if isinstance(value, dict):
        titles, indices = value.get('title', []), value.get('sent_id', [])
        if len(titles) != len(indices):
            raise ValueError('Supporting-fact columns have different lengths.')
        pairs = zip(titles, indices)
    elif isinstance(value, list):
        pairs = value
    else:
        raise ValueError('Invalid supporting facts for evaluation.')
    result = set()
    for title, index in pairs:
        if not isinstance(title, str) or type(index) is not int or index < 0:
            raise ValueError('Invalid supporting-fact title/sentence ID.')
        result.add((title, index))
    return result


def evidence_metrics(result, supporting_facts):
    """Gold facts are read only AFTER a method has finished; never control retrieval."""
    gold = supporting_facts_set(supporting_facts)
    def coverage(evidence):
        visible = {(p['title'], sent_id) for p in evidence for sent_id in p['sentence_ids']}
        return len(visible & gold) / len(gold) if gold else None
    first = coverage(result['evidence_first'])
    final = coverage(result['evidence_final'])
    return {'supporting_fact_coverage_first': first, 'supporting_fact_coverage_final': final,
            'supporting_fact_count': len(gold),
            'premature_stopping': (bool(result['stopped_after_first'] and first < 1)
                                   if first is not None else None)}


def answer_metrics(answer, gold):
    f1 = squad_f1(answer, gold)
    return {'f1': f1, 'em': squad_em(answer, gold), 'acc': float(f1 >= 0.5)}
