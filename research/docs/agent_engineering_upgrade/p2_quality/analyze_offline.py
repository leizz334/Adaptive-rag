"""Recompute tool counts directly from persisted executor observations."""

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.memory_ablation import REFERENCE_IDS, summarize


def aggregate(rows):
    metrics = summarize(rows)
    calls = [c for r in rows for c in r["evidence"]["tool_calls"]]
    extra = sum(t["scores"]["unnecessary_tool_calls"] for r in rows for t in r["evidence"]["turns"])
    metrics.update(
        tool_calls=len(calls),
        tool_calls_per_task=len(calls) / len(rows) if rows else None,
        scorer_redundant_tool_calls=extra,
        wrong_arguments=sum(
            t["scores"].get("tool_argument_accuracy") is not None
            and t["scores"]["tool_argument_accuracy"] < 1
            for r in rows
            for t in r["evidence"]["turns"]
        ),
        executed_invalid_argument_calls=sum(
            c.get("failure_kind") == "invalid_arguments" for c in calls
        ),
        calls_by_tool=dict(Counter(c["name"] for c in calls)),
        failures=[
            dict(case=r["case_id"], reasons=r["reasons"]) for r in rows if r["status"] != "PASS"
        ],
    )
    return metrics


def analyze(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[4]
    original_ids = {
        c["id"]
        for c in json.loads((root / "eval/dataset/agent_v2_extended.json").read_bytes())[
            "scenarios"
        ]
    }
    result = []
    for arm in data["arms"]:
        rows = arm["results"]
        owner7 = {"foreign_order"} | {
            f"owner_ORD1000{i}_{u}" for i in (1, 2, 3) for u in ("other", "anonymous")
        }
        groups = dict(
            original80=[r for r in rows if r["case_id"] in original_ids],
            original7=[r for r in rows if r["case_id"] in REFERENCE_IDS],
            owner7=[r for r in rows if r["case_id"] in owner7],
            diagnostic12=[r for r in rows if r["case_id"].startswith("hr")],
            long_window=[r for r in rows if r["case_id"] == "p2_long_window"],
        )
        # New case IDs are read from the separate frozen schema only after release.
        if any(
            r["case_id"] not in {r2["case_id"] for group in groups.values() for r2 in group}
            for r in rows
        ):
            groups["new_unseen"] = [
                r
                for r in rows
                if r["case_id"] not in {r2["case_id"] for group in groups.values() for r2 in group}
            ]
        result.append(
            dict(
                mode=arm["mode"],
                provider=arm["provider"],
                groups={k: aggregate(v) for k, v in groups.items()},
            )
        )
    return dict(
        arms=result,
        note="Recomputed from evidence.tool_calls; initial C0 embedded calls_per_task used wrong nesting and must be ignored. Scores and raw calls unchanged.",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a fresh output")
    args.output.write_bytes(
        (json.dumps(analyze(args.results), ensure_ascii=False, indent=2) + "\n").encode()
    )
