"""Strict structural contracts, not a proof of semantic correctness.

The first release deliberately accepts rooted trees rather than general DAGs.
Each prerequisite has exactly one consumer and occupies exactly one input slot.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import re
from typing import Any
from .config import MAX_PLAN_NODES


TYPES = frozenset({"person", "organization", "place", "date", "number", "work", "boolean", "other"})
SLOT_PATTERN = re.compile(r"\{\{(q[1-9][0-9]{0,2})\}\}")
ID_PATTERN = re.compile(r"q[1-9][0-9]{0,2}")


def normalize_json_wrapper(raw: str) -> tuple[str, str]:
    """Remove only a complete fence or one stray closing fence after an object.

    This does not repair JSON contents. The strict decoder must still accept the
    entire remaining text; prose, duplicate keys and additional objects fail.
    """
    if not isinstance(raw, str):
        raise ValueError("Model output must be a JSON string.")
    if len(raw) > 1_000_000:
        raise ValueError("Model output exceeds the JSON size limit.")
    cleaned = raw.strip()
    normalization = 'none'
    if cleaned.startswith("```"):
        fenced = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", cleaned, re.DOTALL)
        if not fenced:
            raise ValueError("Expected one complete JSON fence, without surrounding prose.")
        cleaned = fenced.group(1)
        normalization = 'complete_fence_removed'
    elif cleaned.startswith('{') and re.search(r'}\s*```$', cleaned):
        cleaned = cleaned[:-3].rstrip()
        normalization = 'closing_fence_removed'
    return cleaned, normalization


def parse_json_object(raw: str) -> dict:
    """Parse one JSON object; reject duplicate keys, NaN and trailing prose."""
    cleaned, _ = normalize_json_wrapper(raw)

    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}.")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"Non-finite JSON constant is forbidden: {value}.")

    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Non-finite JSON number is forbidden.")
        return parsed

    try:
        data = json.loads(cleaned, object_pairs_hook=no_duplicates, parse_constant=reject_constant,
                          parse_float=finite_float)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Expected one JSON object, not null, a list, or a scalar.")
    return data


def validate_plan(data: Any, max_nodes: int = MAX_PLAN_NODES) -> dict:
    """Validate a typed rooted tree and return deterministic dependency order.

    This never labels the decomposition semantically correct. A one-node plan
    may be an appropriate atomic question or an inadequate undecomposed question.
    """
    if type(max_nodes) is not int or not 1 <= max_nodes <= 999:
        raise ValueError("max_nodes must be an integer in 1..999.")
    if not isinstance(data, dict) or set(data) != {"nodes", "final"}:
        raise ValueError("Plan must contain exactly nodes and final.")
    nodes = data["nodes"]
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= max_nodes:
        raise ValueError(f"Plan must contain 1..{max_nodes} nodes.")
    by_id = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != {"id", "question", "dependencies", "answer_type"}:
            raise ValueError(f"Node {index} requires exactly id, question, dependencies, answer_type.")
        nid = node["id"]
        if not isinstance(nid, str) or not ID_PATTERN.fullmatch(nid):
            raise ValueError(f"Node {index}: id must be a q1..q999 string.")
        if nid in by_id:
            raise ValueError(f"Duplicate node id: {nid}.")
        question = node["question"]
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError(f"{nid}: question must contain 1..2000 characters.")
        kind, deps = node["answer_type"], node["dependencies"]
        if not isinstance(kind, str) or kind not in TYPES:
            raise ValueError(f"{nid}: answer_type must be one of {sorted(TYPES)}.")
        if not isinstance(deps, dict):
            raise ValueError(f"{nid}: dependencies must map node IDs to expected answer types.")
        for dep, expected in deps.items():
            if not isinstance(dep, str) or not ID_PATTERN.fullmatch(dep):
                raise ValueError(f"{nid}: dependency IDs must be q1..q999 strings.")
            if not isinstance(expected, str) or expected not in TYPES:
                raise ValueError(f"{nid}: dependency {dep} has an invalid expected type.")
        occurrences = Counter(SLOT_PATTERN.findall(question))
        if any(character in SLOT_PATTERN.sub("", question) for character in "{}"):
            raise ValueError(f"{nid}: malformed or unknown placeholder; use literal {{{{q1}}}} slots.")
        if set(occurrences) != set(deps):
            raise ValueError(f"{nid}: placeholders and declared dependencies must match exactly.")
        if any(count != 1 for count in occurrences.values()):
            raise ValueError(f"{nid}: each dependency placeholder must occur exactly once in strict-tree mode.")
        if nid in deps:
            raise ValueError(f"{nid}: self-dependency is forbidden.")
        by_id[nid] = {"id": nid, "question": question.strip(), "dependencies": dict(deps), "answer_type": kind}

    final = data["final"]
    if not isinstance(final, str) or final not in by_id:
        raise ValueError("final must name an existing node.")
    consumers = Counter()
    for node in by_id.values():
        for dep, expected in node["dependencies"].items():
            if dep not in by_id:
                raise ValueError(f"{node['id']}: unknown dependency {dep}.")
            if expected != by_id[dep]["answer_type"]:
                raise ValueError(f"{node['id']}: dependency {dep} expects {expected}, but returns {by_id[dep]['answer_type']}.")
            consumers[dep] += 1
    if consumers[final] != 0:
        raise ValueError("final must be the root and cannot be consumed by another node.")
    for nid in by_id:
        if nid != final and consumers[nid] != 1:
            raise ValueError(f"{nid}: each non-root node needs exactly one consumer; no shared or orphan nodes.")

    ordered, resolved = [], set()
    while len(ordered) < len(by_id):
        ready = [node for nid, node in by_id.items()
                 if nid not in resolved and set(node["dependencies"]) <= resolved]
        if not ready:
            raise ValueError("Cyclic dependencies are forbidden.")
        for node in ready:
            ordered.append(node)
            resolved.add(node["id"])
    # Root/consumer invariants plus acyclicity imply every node reaches final.
    return {"nodes": ordered, "final": final}



def expand_plan(plan: dict, max_chars: int = 30_000) -> str:
    """Display formal nesting only; do not claim natural-language equivalence."""
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError("max_chars must be a positive integer.")
    validated = validate_plan(plan, max_nodes=999)
    expanded = {}
    for node in validated["nodes"]:
        text = SLOT_PATTERN.sub(lambda match: f"[{match.group(1)}: {expanded[match.group(1)]}]", node["question"])
        if len(text) > max_chars:
            raise ValueError("Expanded plan exceeds the display-size limit.")
        expanded[node["id"]] = text
    return expanded[validated["final"]]


def expand_typed_plan(plan: dict, max_chars: int = 30_000) -> str:
    """One nested representation; each node/question/type appears exactly once.

    A strict tree consumes each prerequisite once. A slot is replaced by an
    explicitly marked answer expression, not by an invented answer. Question
    text outside slots is untouched. Overlong displays fail instead of clipping.
    """
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError("max_chars must be a positive integer.")
    validated = validate_plan(plan, max_nodes=999)
    expanded = {}
    for node in validated['nodes']:
        question = SLOT_PATTERN.sub(lambda m: expanded[m.group(1)], node['question'])
        text = f"[answer {node['id']}:{node['answer_type']} | {question}]"
        if len(text) > max_chars:
            raise ValueError('Expanded typed plan exceeds the display-size limit; nothing was truncated.')
        expanded[node['id']] = text
    return expanded[validated['final']]
