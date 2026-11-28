"""Recompute RAG generation metrics and reconcile the recorded DeepSeek receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from eval import rerank_ablation as original
from eval.release.shared.budget import RATE, cny, metered_usage

USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
)
GOLD = "2de6a3676428d57ecc45379889f4e79403a343711ba93bca11dda2d05534a3d9"
TAIPEI = timezone(timedelta(hours=8))


def load(path: Path):
    return json.loads(path.read_bytes())


def ratio(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def view(rows: list[dict]) -> dict:
    counts = Counter(row["judgment"]["status"] for row in rows)
    valid = counts["SUPPORTED"] + counts["UNSUPPORTED"]
    correct = [item["correctness"]["correct"] for item in rows]
    evidence = [item["correctness"]["evidence_covers_all_conditions"] for item in rows]
    complete_verdicts = [
        answer is True and context is True
        for answer, context in zip(correct, evidence, strict=True)
        if answer is not None and context is not None
    ]
    return {
        "n": len(rows),
        "rounds": {
            str(count): cases
            for count, cases in sorted(Counter(len(row["rounds"]) for row in rows).items())
        },
        "faithfulness": ratio(counts["SUPPORTED"], valid),
        "hallucination": ratio(counts["UNSUPPORTED"], valid),
        "judge_coverage": ratio(valid, len(rows)),
        "faithfulness_statuses": dict(sorted(counts.items())),
        "answer_approved_by_reference_judge": ratio(
            sum(value is True for value in correct), sum(value is not None for value in correct)
        ),
        "answer_correct_with_complete_evidence": ratio(
            sum(complete_verdicts), len(complete_verdicts)
        ),
        "retrieval_covers_all_conditions": ratio(
            sum(value is True for value in evidence), sum(value is not None for value in evidence)
        ),
        "all_keywords_hit": ratio(sum(row["keyword_hit"] for row in rows), len(rows)),
        "original_summary": original.summarize(rows),
    }


def summarize(root: Path) -> dict:
    gold_bytes = original.RAG_PATH.read_bytes()
    assert hashlib.sha256(gold_bytes).hexdigest() == GOLD
    gold = {item["id"]: item for item in original.load_jsonl(original.RAG_PATH)}
    historical_knowledge = load(Path("eval/release/evidence/rag/natural/manifest.json"))[
        "knowledge_sha256"
    ]
    knowledge = {
        path.relative_to("knowledge").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path("knowledge").rglob("*.md")
    }
    assert knowledge == historical_knowledge
    receipts = load(root / "requests.json")
    totals = receipts["totals"]
    assert len(receipts["requests"]) == totals["attempts"] <= totals["max_requests"] <= 420
    assert Decimal(totals["actual_cost_cny"]) <= Decimal(totals["cap_cny"]) <= Decimal("0.60")
    if batches := receipts.get("batches"):
        natural, forced = batches
        assert all(Decimal(batch["outstanding_reserve_cny"]) == 0 for batch in batches)
        assert Decimal(natural["actual_cost_cny"]) + Decimal(forced["cap_cny"]) == Decimal(
            totals["cap_cny"]
        )
        assert natural["attempts"] + forced["max_requests"] == totals["max_requests"]
        assert sum(item["attempts"] for item in batches) == totals["attempts"]
        assert sum(Decimal(item["actual_cost_cny"]) for item in batches) == Decimal(
            totals["actual_cost_cny"]
        )
    by_job: dict[str, list] = defaultdict(list)
    paid = 0
    tokens: Counter = Counter()
    models: set = set()
    fingerprints: set = set()
    weekend = set()
    for row in receipts["requests"]:
        assert row["status"] == "billed" and row["http_status"] == 200
        assert row["usage"] == metered_usage(row["response"])
        assert row["request"]["model"] == row["response"]["model"] == "deepseek-flash"
        assert row["request"]["thinking"] == {"type": "disabled"}
        assert row["endpoint"] == "/chat/completions"
        models.add(row["response"]["model"])
        fingerprints.add(row["response"].get("system_fingerprint"))
        tokens.update(row["usage"])
        actual = (
            row["usage"]["prompt_cache_hit_tokens"] * RATE["cache_hit"]
            + row["usage"]["prompt_cache_miss_tokens"] * RATE["cache_miss"]
            + row["usage"]["completion_tokens"] * RATE["completion"]
        )
        assert actual == row["actual"]
        paid += actual
        weekend.add(datetime.fromisoformat(row["admitted"]).astimezone(TAIPEI).weekday() >= 5)
        by_job[row["scope"]["job"]].append(row)
    assert totals["actual_cost_cny"] == cny(paid)
    assert not paid % 2
    results = {
        "gold_sha256": GOLD,
        "knowledge_files": len(knowledge),
        "requests": len(receipts["requests"]),
        "usage": dict(tokens),
        "model_aliases": sorted(models),
        "model_fingerprints": sorted(fingerprints, key=str),
        "peak_price_budget_cny": cny(paid),
        "weekend_off_peak_price_cny": cny(paid // 2) if weekend == {True} else None,
        "settings": {},
    }
    for mode in ("natural", "forced"):
        cases = original.load_jsonl(root / mode / "A.jsonl")
        ids = {row["id"] for row in cases}
        manifest = load(root / mode / "manifest.json")
        expected = {
            key
            for key, row in gold.items()
            if mode == "natural" or len(row["relevant_doc_ids"]) > 1
        }
        assert ids == expected == set(manifest["case_ids"]) and len(ids) == len(cases)
        assert manifest["gold_sha256"] == GOLD and manifest["knowledge_sha256"] == knowledge
        assert manifest["kb_chunk_count"] == 127
        assert (
            manifest["corpus_sha256"]
            == "e8393639c6f093da26a6788926634a816febb5a90410992498f4d45e93851114"
        )
        for case in cases:
            row = gold[case["id"]]
            assert case["query"] == row["query"]
            relevant = set(row["relevant_doc_ids"])
            ranked = list(dict.fromkeys(item["doc"] for item in case["ranked"]))
            ranked_chunks = {item["id"]: item["doc"] for item in case["ranked"]}
            context_docs = {ranked_chunks[item] for item in case["context_ids"]}
            assert case["ranking"] == original.ranking_metrics(relevant, ranked)
            assert case["gold_doc_ids"] == sorted(relevant)
            assert case["cohort"] == ("multi" if len(relevant) > 1 else "single")
            assert case["context_gold_doc_recall"] == len(context_docs & relevant) / len(relevant)
            assert case["all_gold_docs_in_context"] == (relevant <= context_docs)
            assert case["keyword_hit"] == original._keyword_hit(
                case["answer"], row["gold_answer_contains"]
            )
            captured = case["pipeline_calls"] + case["evaluation_calls"]
            saved = by_job.pop(f"{mode}:{row['id']}")
            assert len(captured) == len(saved)
            for observation, receipt in zip(captured, saved, strict=True):
                assert {key: observation[key] for key in USAGE_KEYS} == receipt["usage"]
        groups = {
            name: view([row for row in cases if name == "all" or row["cohort"] == name])
            for name in ("all", "single", "multi")
        }
        legacy = load(root / mode / "A-summary.json")
        assert {name: summary["original_summary"] for name, summary in groups.items()} == legacy
        results["settings"][mode] = groups
    assert not by_job
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = summarize(args.evidence)
    summary = args.evidence / "generation-summary.json"
    if args.verify:
        assert load(summary) == result
    else:
        summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified": True, "requests": result["requests"]}))


if __name__ == "__main__":
    main()
