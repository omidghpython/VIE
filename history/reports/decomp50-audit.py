"""Offline audit of decomp50 logs against the previously reviewed operadic_rag code.

No model/backend is constructed and no fresh inference is performed. The reference
code is a comparator, not a claim about the exact source used in the logged run.
Usage: python audit_decomp50.py --results EXTRACTED_DECOMP50 --reference-code
EXTRACTED_OPERADIC_RAG --baseline-samples MAX4_SAMPLES_JSON --output AUDIT_JSON
"""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jsonl(path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10)
    return a == b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--reference-code", type=Path, required=True)
    parser.add_argument("--baseline-samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.reference_code.resolve()))
    from oprag import prompts_tree as P
    from oprag.decomp_eval import answer_correct, summarize, render_review, render_summary
    from oprag.scoring import normalize_answer, exact_match, f1_score
    from oprag.tree import build_tree, check_against_gold
    from oprag.util import clean_answer, parse_json_object

    root = args.results
    rows = jsonl(root / "decomposition.jsonl")
    calls = jsonl(root / "llm_calls.jsonl")
    baseline = json.loads(args.baseline_samples.read_text(encoding="utf-8"))
    by_qid = collections.defaultdict(list)
    for call in calls:
        by_qid[call["qid"]].append(call)
    problems = []
    counts = collections.Counter()
    metrics_rows = []

    def check(test, label):
        if not test:
            problems.append(label)

    check(len({r["id"] for r in rows}) == len(rows), "duplicate result IDs")
    check(set(by_qid) == {r["id"] for r in rows}, "call/result ID set")
    for index, row in enumerate(rows, 1):
        qid = row["id"]
        checkpoint = json.loads((root / "state/questions" / (qid + ".json")).read_text(encoding="utf-8"))
        check(checkpoint["status"] == "completed", f"{index}: checkpoint status")
        check(checkpoint["record"] == row, f"{index}: checkpoint record")
        check(checkpoint["llm_calls"] == by_qid[qid], f"{index}: checkpoint calls")
        counts["checkpoints_replayed"] += 1
        generations = [c for c in by_qid[qid] if c["stage"].startswith("decompose")]
        check(len(generations) == len(row["attempt_history"]) == row["attempts"], f"{index}: attempts")
        tree = None
        previous = None
        for attempt, (call, history) in enumerate(zip(generations, row["attempt_history"]), 1):
            expected_user = (P.decompose_user(row["question"]) if attempt == 1 else
                             P.decompose_repair_user(row["question"], previous["raw"], previous["problems"]))
            check(call["system"] == P.DECOMPOSE_TREE_SYSTEM, f"{index}/{attempt}: generation system")
            check(call["user"] == expected_user, f"{index}/{attempt}: generation user")
            check(call["stage"] == ("decompose" if attempt == 1 else "decompose_retry"), f"{index}/{attempt}: stage")
            check(call["response"] == history["raw"], f"{index}/{attempt}: raw output")
            tree, errors, warnings = build_tree(row["question"], parse_json_object(history["raw"]))
            check(errors == history["problems"], f"{index}/{attempt}: structural errors")
            check(warnings == history["warnings"], f"{index}/{attempt}: warnings")
            counts["generation_attempts_replayed"] += 1
            previous = history
        check((tree.to_dict() if tree else None) == row["tree"], f"{index}: final tree")
        check(row["first_attempt_valid"] == (not row["attempt_history"][0]["problems"]), f"{index}: first valid")
        check(row["warnings"] == (previous["warnings"] if tree else []), f"{index}: final warnings")
        gold_checks = check_against_gold(tree, row["gold_type"], row["support_titles"]) if tree else None
        check(gold_checks == row["gold_checks"], f"{index}: gold checks")
        check(row["tree_valid"] == bool(tree and gold_checks["structure_ok"]), f"{index}: tree_valid")
        evaluations = [c for c in by_qid[qid] if c["stage"].startswith("eval_")]
        if not tree:
            check(row["exec"] is None and not evaluations, f"{index}: no tree execution")
        else:
            exe = row["exec"]
            stage_calls = {c["stage"]: c for c in evaluations}
            check(len(stage_calls) == len(tree.leaves) + 2 == len(evaluations), f"{index}: eval stages")
            context = stage_calls["eval_direct"]["user"].split("\n\nQuestion: ", 1)[0].removeprefix("Passages:\n")
            leaf_answers = []
            for leaf_index, leaf in enumerate(tree.leaves, 1):
                call = stage_calls[f"eval_leaf{leaf_index}"]
                check(call["system"] == P.EXEC_LEAF_SYSTEM and call["user"] == P.exec_leaf_user(leaf, context), f"{index}: leaf{leaf_index} prompt")
                leaf_answers.append(clean_answer(call["response"]))
            check(leaf_answers == exe["leaf_answers"], f"{index}: leaf responses")
            filled = tree.fill_root(leaf_answers)
            check(filled == exe["root_filled"], f"{index}: filled root")
            root_call = stage_calls["eval_root"]
            expected_system = P.EXEC_LEAF_SYSTEM if tree.kind == "bridge" else P.EXEC_ROOT_SYSTEM
            expected_user = P.exec_leaf_user(filled, context) if tree.kind == "bridge" else P.exec_root_user(filled)
            check(root_call["system"] == expected_system and root_call["user"] == expected_user, f"{index}: root prompt")
            direct = stage_calls["eval_direct"]
            check(direct["system"] == P.EXEC_LEAF_SYSTEM and direct["user"] == P.exec_leaf_user(row["question"], context), f"{index}: direct prompt")
            check(clean_answer(root_call["response"]) == exe["final"], f"{index}: root answer")
            check(clean_answer(direct["response"]) == exe["direct_oracle"], f"{index}: direct answer")
            for field, correct_key in [("final", "final_correct"), ("direct_oracle", "direct_oracle_correct")]:
                check(answer_correct(exe[field], row["gold_answer"]) == exe[correct_key], f"{index}: {correct_key}")
            check(close(f1_score(exe["final"], row["gold_answer"]), exe["final_f1"]), f"{index}: final_f1")
            # Passage bodies only: the earlier implementation excludes titles and [n] prefixes.
            paragraphs = [line.split(": ", 1)[1] for line in context.splitlines() if line.startswith("[")]
            ctx_norm = normalize_answer(" ".join(paragraphs))
            grounded = [bool(normalize_answer(a)) and normalize_answer(a) != "unknown" and
                        f" {normalize_answer(a)} " in f" {ctx_norm} " for a in leaf_answers]
            check(grounded == exe["leaf_answers_grounded"], f"{index}: verbatim grounding")
            counts["evaluation_calls_replayed"] += len(evaluations)
            metrics_rows.append({"index": index, "id": qid,
                                 "decomposition_em": exact_match(exe["final"], row["gold_answer"]),
                                 "direct_em": exact_match(exe["direct_oracle"], row["gold_answer"]),
                                 "decomposition_f1": f1_score(exe["final"], row["gold_answer"]),
                                 "direct_f1": f1_score(exe["direct_oracle"], row["gold_answer"])})
        check(row["decomp_ok_auto"] == bool(row["tree_valid"] and row["exec"] and row["exec"]["final_correct"]), f"{index}: auto verdict")
        for field, selected in [("cost_decomposition", generations), ("cost_evaluation", evaluations)]:
            cost = {"llm_calls": len(selected), "prompt_tokens": sum(c["prompt_tokens"] for c in selected),
                    "completion_tokens": sum(c["completion_tokens"] for c in selected),
                    "total_tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in selected),
                    "time_s": sum(c["latency_s"] for c in selected)}
            check(close(cost, row[field]), f"{index}: {field}")

    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    reproduced = summarize(rows)
    reproduced["errors"] = sum(bool(r.get("error")) for r in rows)
    check(close(reproduced, summary), "summary JSON reproduction")
    check(render_summary(summary) == (root / "summary.md").read_text(encoding="utf-8"), "summary Markdown reproduction")
    check(render_review(rows) == (root / "review.md").read_text(encoding="utf-8"), "review Markdown reproduction")
    with zipfile.ZipFile(root / "decomposition_results.zip") as inner:
        check(inner.testzip() is None, "inner ZIP CRC")
        for name in inner.namelist():
            check(inner.read(name) == (root / name).read_bytes(), "inner/outer: " + name)
        counts["inner_files_verified"] = len(inner.namelist())
    with (root / "review.csv").open(encoding="utf-8-sig", newline="") as handle:
        human = list(csv.DictReader(handle))
    human_marked = sum(any(v.strip() for k, v in r.items() if k.startswith("human")) for r in human)
    pairs = collections.Counter((r["exec"]["final_correct"], r["exec"]["direct_oracle_correct"]) for r in rows if r["exec"])
    overlap = [{"id": r["id"], "external_index": i, "baseline_index": j, "question": r["question"]}
               for i, r in enumerate(rows, 1) for j, b in enumerate(baseline, 1) if r["id"] == b["id"]]
    totals = {}
    for name, selected in [("decomposition", [c for c in calls if c["stage"].startswith("decompose")]),
                           ("evaluation", [c for c in calls if c["stage"].startswith("eval_")]), ("all", calls)]:
        totals[name] = {"calls": len(selected), "prompt_tokens": sum(c["prompt_tokens"] for c in selected),
                        "completion_tokens": sum(c["completion_tokens"] for c in selected),
                        "total_tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in selected),
                        "summed_call_seconds": sum(c["latency_s"] for c in selected)}
    result = {"all_checks_passed": not problems, "mismatches": problems, "verified": dict(counts),
              "source_identity_claim": "Behavior/prompt compatibility with earlier reviewed code only; runtime source not supplied.",
              "reference_files_sha256": {str(p.relative_to(args.reference_code)): sha(p.read_bytes())
                                         for p in sorted((args.reference_code / "oprag").glob("*.py"))},
              "input_files_sha256": {p.name: sha(p.read_bytes()) for p in sorted(root.iterdir()) if p.is_file()},
              "settings": json.loads((root / "state/manifest.json").read_text(encoding="utf-8"))["settings"],
              "baseline_n": len(baseline), "baseline_types": dict(collections.Counter(r["type"] for r in baseline)),
              "external_n": len(rows), "overlap": overlap,
              "question_text_overlap": len({r["question"].strip().casefold() for r in rows} & {r["question"].strip().casefold() for r in baseline}),
              "summary_reproduced": reproduced, "attempts": dict(collections.Counter(r["attempts"] for r in rows)),
              "stages": dict(collections.Counter(c["stage"] for c in calls)), "totals": totals,
              "estimated_token_calls": sum(c["estimated"] for c in calls), "human_review_rows_marked": human_marked,
              "paired_outcomes": {f"decomp_{a}_direct_{b}": n for (a, b), n in sorted(pairs.items())},
              "normalized_answer_metrics_46_executed": {k: sum(r[k] for r in metrics_rows) / len(metrics_rows)
                     for k in ["decomposition_em", "direct_em", "decomposition_f1", "direct_f1"]},
              "per_question_answer_metrics": metrics_rows,
              "no_tree_indices": [i for i, r in enumerate(rows, 1) if not r["tree"]],
              "unknown_leaf_indices": [i for i, r in enumerate(rows, 1) if r["exec"] and any(a.casefold() == "unknown" for a in r["exec"]["leaf_answers"])],
              "correct_with_unknown_leaf_indices": [i for i, r in enumerate(rows, 1) if r["exec"] and r["exec"]["final_correct"] and any(a.casefold() == "unknown" for a in r["exec"]["leaf_answers"])],
              "model_calls_during_audit": 0}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["all_checks_passed", "mismatches", "verified", "totals", "normalized_answer_metrics_46_executed", "overlap"]}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
