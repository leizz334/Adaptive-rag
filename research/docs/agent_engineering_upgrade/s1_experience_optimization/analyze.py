"""Post-run summary; recomputes the frozen scorer and keeps supplemental audits separate."""

import csv
import json
import math
import statistics

from app.main import create_app  # noqa: F401
from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import PRICING, digest

from .common import HERE, RUN, read, save, sha, verify_freeze
from .meter import Ledger
from .scoring import score


def main():
    frozen = verify_freeze()
    ledger = Ledger(RUN)
    ledger.safe()
    rows = []
    pairs = []
    packet = []
    named_audits = []
    assert len(ledger.rows) == 60
    assert all(r["source_freeze_sha256"] == digest(frozen) for r in ledger.rows)
    for task in read(HERE / "tasks.json")["tasks"]:
        captures = {
            arm: read(RUN / (task["id"] + "_" + arm + ".json")) for arm in ["E0", "E1", "E2"]
        }
        assert (RUN / (task["id"] + "_TRIPLET_COMPLETE.json")).exists()
        assert all(
            c["query"] == task["query"]
            and c["business_before"] == captures["E0"]["business_before"]
            and c["business_before"] == c["business_after"]
            and c["initial_session_empty"]
            for c in captures.values()
        )
        assert all(
            c["scores"] == score(task, c["body"], c["tools"], True) for c in captures.values()
        )
        values = {arm: c["scores"] for arm, c in captures.items()}
        pair = {
            "case": task["id"],
            "split": task["split"],
            "complete": True,
            "equal_query_business_cleanhistory": True,
            "execution": {a: v["execution_success_proxy"] for a, v in values.items()},
            "bounded": {a: v["bounded_e2e_proxy"] for a, v in values.items()},
            "bounded_effect_eligible": all(
                v["bounded_e2e_proxy"] is not None for v in values.values()
            ),
        }
        for arm, c in captures.items():
            events = [e for e in c["events"] if e["kind"] == "experience_planner"]
            assert len(events) == 1 and events[0]["catalog_unchanged"]
            assert (
                (events[0]["before_sha256"] == events[0]["after_sha256"])
                if arm in ["E0", "E1"]
                else events[0]["injected"] in [1, 2]
            )
            group = [r for r in ledger.rows if r["group"] == task["id"] + "_" + arm]
            cost = sum(
                (
                    r["usage"]["prompt_tokens"] * PRICING["input"]
                    + r["usage"]["completion_tokens"] * PRICING["output"]
                )
                / 1e6
                for r in group
            )
            item = {
                "case": task["id"],
                "split": task["split"],
                "arm": arm,
                "requests": len(group),
                "tokens": sum(r["usage"]["total_tokens"] for r in group),
                "input_tokens": sum(r["usage"]["prompt_tokens"] for r in group),
                "output_tokens": sum(r["usage"]["completion_tokens"] for r in group),
                "cost_upper_usd": cost,
                "latency_ms": c["latency_ms"],
                "injected_lessons": events[0]["injected"],
                "selected_families": [v["family"] for v in events[0]["selected"]],
                "tool_sequence": [
                    {k: t[k] for k in ["name", "arguments", "success"]} for t in c["tools"]
                ],
                "scores": c["scores"],
                "prompt_before": events[0]["before_sha256"],
                "prompt_after": events[0]["after_sha256"],
            }
            rows.append(item)
            capture_path = RUN / (task["id"] + "_" + arm + ".json")
            packet.append(
                {
                    "case": task["id"],
                    "split": task["split"],
                    "arm": arm,
                    "question": task["query"],
                    "answer": c["body"]["answer"],
                    "actual_tools": c["tools"],
                    "source": str(capture_path.relative_to(HERE)),
                    "sha256": sha(capture_path),
                    "frozen_bounded_metric": c["scores"],
                    "human_factual_correctness": None,
                    "human_completeness": None,
                    "human_faithfulness": None,
                    "human_overall": None,
                    "reviewer": None,
                    "review_time": None,
                }
            )
        # This literal requested-name audit is POST-HOC and does not overwrite the frozen score.
        expected_names = (
            [line["name"] for o in task["orders"] for line in o["items"]]
            if any(t["name"] == "get_order_items" for t in task["required_tools"])
            else []
        )
        if expected_names:
            # Only the order whose item tool was requested belongs to this subgoal.
            requested_ids = {
                t["arguments"]["order_id"]
                for t in task["required_tools"]
                if t["name"] == "get_order_items"
            }
            expected_names = [
                line["name"]
                for o in task["orders"]
                if o["order_id"] in requested_ids
                for line in o["items"]
            ]
            named_audits.append(
                {
                    "case": task["id"],
                    "split": task["split"],
                    "method": "POST_HOC_LITERAL_REQUESTED_NAMES_FROM_PREDECLARED_GOLD",
                    "expected_names": expected_names,
                    "presence": {
                        a: [name in c["body"]["answer"] for name in expected_names]
                        for a, c in captures.items()
                    },
                    "complete": {
                        a: all(name in c["body"]["answer"] for name in expected_names)
                        for a, c in captures.items()
                    },
                    "human_semantic_truth": False,
                }
            )
        pairs.append(pair)
    effects = []
    for split in ["development", "independent"]:
        for metric in ["execution", "bounded"]:
            included = [
                p
                for p in pairs
                if p["split"] == split and (metric == "execution" or p["bounded_effect_eligible"])
            ]
            for baseline in ["E0", "E1"]:
                effects.append(
                    {
                        "split": split,
                        "metric": metric,
                        "comparison": baseline + "->E2",
                        "n_complete_eligible_pairs": len(included),
                        "positive": sum(
                            not p[metric][baseline] and p[metric]["E2"] for p in included
                        ),
                        "negative": sum(
                            p[metric][baseline] and not p[metric]["E2"] for p in included
                        ),
                    }
                )
    resources = {}
    for arm in ["E0", "E1", "E2"]:
        cells = [r for r in rows if r["arm"] == arm]
        resources[arm] = {
            "n": len(cells),
            "requests": sum(r["requests"] for r in cells),
            "total_tokens": sum(r["tokens"] for r in cells),
            "mean_tokens": statistics.mean(r["tokens"] for r in cells),
            "mean_latency_ms": statistics.mean(r["latency_ms"] for r in cells),
            "cost_upper_usd": sum(r["cost_upper_usd"] for r in cells),
        }
    latency = sorted(r["latency_ms"] for r in ledger.rows)
    stage_digests = {}
    for arm in ["E0", "E1", "E2"]:
        stage_digests[arm] = [
            {k: r[k] for k in ["stage", "prompt_sha256"]}
            for r in ledger.rows
            if r["group"] == "S1EXI01_" + arm
        ]
    output = {
        "phase": "S1-EX",
        "frozen_scorer_preserved": True,
        "complete_triplets": 4,
        "pairs": pairs,
        "rows": rows,
        "effects": effects,
        "resource_summary": resources,
        "ledger": ledger.totals(),
        "input_tokens": sum(r["usage"]["prompt_tokens"] for r in ledger.rows),
        "output_tokens": sum(r["usage"]["completion_tokens"] for r in ledger.rows),
        "model_request_latency_mean_ms": statistics.mean(latency),
        "model_request_latency_p95_ms": latency[math.ceil(0.95 * len(latency)) - 1],
        "posthoc_requested_name_audit": named_audits,
        "I01_stage_prompt_digests": stage_digests,
        "benefit": "NOT_ESTABLISHED",
        "causal_negative_transfer": "NOT_ESTABLISHED_SMALL_N_MODEL_VARIABILITY",
        "full_semantics": "NOT_ASSESSED",
        "production_active": False,
    }
    save(HERE / "evidence/ex2_results.json", output)
    save(HERE / "semantic_review_packet.json", {"human_fields_blank": True, "items": packet})
    with (HERE / "comparison.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "case",
            "split",
            "arm",
            "execution_success_proxy",
            "bounded_e2e_proxy",
            "requests",
            "tokens",
            "cost_upper_usd",
            "latency_ms",
            "injected_lessons",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{
                        k: row[k]
                        for k in fields
                        if k not in ["execution_success_proxy", "bounded_e2e_proxy"]
                    },
                    "execution_success_proxy": row["scores"]["execution_success_proxy"],
                    "bounded_e2e_proxy": row["scores"]["bounded_e2e_proxy"],
                }
            )
    with (HERE / "semantic_review_template.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = [
            "case",
            "arm",
            "factual_correctness",
            "completeness",
            "faithfulness",
            "overall",
            "reviewer",
            "review_time",
            "notes",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({"case": v["case"], "arm": v["arm"]} for v in packet)
    print(
        json.dumps(
            {
                "pairs": len(pairs),
                "totals": ledger.totals(),
                "resources": resources,
                "effects": effects,
                "posthoc_name_complete": [
                    {"case": x["case"], "complete": x["complete"]} for x in named_audits
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
