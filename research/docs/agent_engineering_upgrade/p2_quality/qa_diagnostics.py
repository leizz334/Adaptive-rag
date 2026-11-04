"""Offline post-hoc schema validation and per-group cost; never sends HTTP."""

import json
from collections import Counter
from pathlib import Path

from app.agents.nodes.generate import AnswerPayload
from app.guardrails.hallucination import FaithfulnessResult
from app.providers.json_parser import parse_model
from app.schemas.agent import AgentPlan, ComplexityResult, IntentResult

HERE = Path(__file__).resolve().parent


def main():
    run = HERE / "runs/20261104_QA_real_01"
    requests = json.loads((run / "requests.json").read_bytes())
    models = dict(
        intent=IntentResult,
        router=ComplexityResult,
        planner=AgentPlan,
        generate=AnswerPayload,
        judge=FaithfulnessResult,
    )
    groups = {}
    invalid = []
    checked = 0
    for row in requests:
        group = groups.setdefault(
            row["group"],
            dict(
                http=0,
                prompt_tokens=0,
                completion_tokens=0,
                accounted_tokens=0,
                latency_ms=0,
                stages=Counter(),
                errors=[],
                estimated_usd=0,
            ),
        )
        group["http"] += 1
        raw = row.get("usage")
        prompt = raw["prompt_tokens"] if raw else row["reserve_input"]
        completion = raw["completion_tokens"] if raw else row["reserve_output"]
        group["prompt_tokens"] += raw["prompt_tokens"] if raw else 0
        group["completion_tokens"] += raw["completion_tokens"] if raw else 0
        group["accounted_tokens"] += prompt + completion
        group["estimated_usd"] += (prompt * 0.3 + completion * 1.2) / 1000000
        group["latency_ms"] += row.get("latency_ms", 0)
        group["stages"][row["stage"]] += 1
        if row.get("model_error") or row.get("transport_error_type"):
            group["errors"].append(row.get("model_error") or row["transport_error_type"])
        if row.get("http_status") != 200 or row["stage"] not in models:
            continue
        checked += 1
        error = None
        if row.get("model_error") == "truncated":
            error = "TRUNCATED_BEFORE_SCHEMA_PARSE"
        else:
            try:
                parse_model(
                    row["response"]["choices"][0]["message"]["content"], models[row["stage"]]
                )
            except Exception as exc:
                error = type(exc).__name__
        if error:
            invalid.append(
                dict(group=row["group"], sequence=row["sequence"], stage=row["stage"], error=error)
            )
    payload = dict(
        groups=groups,
        posthoc_schema_checked=checked,
        invalid=invalid,
        limitation="Post-hoc completion parse against unchanged production schemas; not a recorded runtime exception span. Probe/unknown stages excluded. No tool plan semantics or hidden reasoning inferred.",
    )
    (run / "per_group_usage_and_schema.json").write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    )
    print(json.dumps(dict(checked=checked, invalid=invalid), ensure_ascii=False))


if __name__ == "__main__":
    main()
