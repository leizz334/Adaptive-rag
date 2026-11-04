"""Derive the QA report from immutable request and scoring checkpoints."""

import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

from app.config.settings import Settings
from eval.memory_ablation import REFERENCE_IDS, summarize
from research.docs.agent_engineering_upgrade.p2_quality.real import DATASET, Ledger, read, write

QUALITY = Path(__file__).resolve().parent
RUN = QUALITY / "runs/20261104_QA_real_01"


def main():
    data, config = read(RUN / "results.json"), read(RUN / "experiment_config.json")
    ledger = Ledger(RUN)
    groups, requests = data["groups"], ledger.rows
    targets = {
        c["id"]: c["turns"][-1]["trajectory"]["required"][0]["arguments"]["order_id"]
        for c in read(DATASET)["scenarios"]
        if c["id"] in REFERENCE_IDS
    }
    metrics = {}
    for mode in config["modes"]:
        rows = [g for g in groups if g["mode"] == mode]
        values = summarize(rows)
        ref = [r for r in rows if r["case_id"] in REFERENCE_IDS]
        correct = 0
        for case in ref:
            turn = max(t["turn"] for t in case["evidence"]["turns"])
            # Original oracle requires a fresh get_order with the original target.
            target = targets[case["case_id"]]
            calls = [c for c in case["evidence"]["tool_calls"] if c["turn"] == turn]
            correct += bool(
                any(
                    c["name"] == "get_order" and c["arguments"].get("order_id") == target
                    for c in calls
                )
                and all(c["arguments"].get("order_id", target) == target for c in calls)
            )
        paid = [r for r in requests if r["group"].endswith(":" + mode)]
        latency = sorted(r["latency_ms"] for r in paid if "latency_ms" in r)
        values.update(
            reference_resolution=f"{correct}/{len(ref)}",
            http=len(paid),
            prompt_tokens=sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in paid),
            completion_tokens=sum((r.get("usage") or {}).get("completion_tokens", 0) for r in paid),
            truncations=sum(r.get("model_error") == "truncated" for r in paid),
            model_errors=dict(Counter(r["model_error"] for r in paid if r.get("model_error"))),
            http_mean_ms=mean(latency) if latency else None,
            http_p95_ms=latency[math.ceil(0.95 * len(latency)) - 1] if latency else None,
            http_total_ms=sum(latency),
            trajectory_valid=mean(
                t["scores"]["trajectory_valid"] for r in rows for t in r["evidence"]["turns"]
            )
            if rows
            else None,
            valid_groups=sum(not r["request_errors"] and r["status"] != "ERROR" for r in rows),
            invalid_output_groups=sum(bool(r["request_errors"]) for r in rows),
            pending_requests=sum(r["status"] != "RESPONSE" for r in paid),
        )
        for key in (
            "estimated_input_utf8_bound",
            "scripted_calls",
            "real_model_tokens",
            "paid_tokens",
        ):
            values.pop(key, None)
        values["reported_real_tokens"] = values["prompt_tokens"] + values["completion_tokens"]
        metrics[mode] = values
    total = ledger.totals()
    errors = [
        dict(
            group=r["group"],
            stage=r.get("stage"),
            error=r.get("model_error"),
            finish=[c.get("finish_reason") for c in r.get("response", {}).get("choices", [])],
        )
        for r in requests
        if r.get("model_error")
    ]
    comparison = {
        case: {
            mode: next(
                (r["status"] for r in groups if r["case_id"] == case and r["mode"] == mode),
                "NOT_RUN",
            )
            for mode in config["modes"]
        }
        for case in config["selected_ids"]
    }
    summary = dict(
        status=data["status"],
        metrics=metrics,
        totals=total,
        errors=errors,
        conversion=comparison,
        total_http_latency_ms=sum(r.get("latency_ms", 0) for r in requests),
        http_failures=sum(r.get("http_status", 200) != 200 for r in requests),
        pending=sum(r["status"] != "RESPONSE" for r in requests),
        transport_errors=dict(
            Counter(r["transport_error_type"] for r in requests if r.get("transport_error_type"))
        ),
    )
    write(RUN / "analysis.json", summary)
    ambient = Settings(_env_file=None)
    fields = [
        "memory_recent_messages",
        "memory_context_max_chars",
        "memory_summary_ttl_seconds",
        "llm_judge_max_tokens",
        "token_budget",
        "max_tool_calls",
        "max_agent_steps",
    ]
    write(
        RUN / "effective_config.json",
        dict(
            fixture={k: getattr(ambient, k) for k in fields},
            temperature=0,
            output_budgets=dict(intent=256, router=256, planner=512, generate=700, judge=512),
            external_tracing=False,
        ),
    )
    write(
        RUN / "validation.json",
        dict(
            real_provider="DeepSeekProvider",
            probe=data["probe"],
            frozen_source=config["source_base"],
            full_pairs=sum(
                all(x != "NOT_RUN" for x in values.values()) for values in comparison.values()
            ),
            unknown_usage=total["unknown_usage_requests"],
            budget_within_limits=total["http_attempts"] <= 350
            and total["accounted_tokens"] <= 300000
            and total["estimated_usd"] <= 3,
            pending=summary["pending"],
            status=data["status"],
        ),
    )
    text = [
        "# P2-QA real paired DeepSeek validation",
        "",
        f"Run `{RUN.name}`; status **{data['status']}**. Official endpoint `{config['endpoint']}`, requested and observed model `deepseek-flash`. Source `{config['source_base']}`. Same application, Prompt, structured-output repair, Planner, tools, Gold, scorer, initial fixture and temperature zero across modes; only Memory changes. Modes rotate by case; each group has a fresh isolated SQLite database and no external tracing.",
        "",
        "Historical baseline (9/15 valid, task2/9, reference0/7, 58,342tokens) is retained as historical reference only. It differs in source/reliability repair/caps/sample validity and is not a causal before/after control. This experiment compares three arms of the same P2 implementation, before QC changes.",
        "",
        "| Mode | Task success (all attempted) | Reference binding | Tool selection | Arguments | Environment | HTTP | Tokens | Truncations |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for mode, m in metrics.items():
        text.append(
            f"|{mode}|{m['passed']}/{m['cases']}|{m['reference_resolution']}|{m['tool_selection']:.3f}|{m['tool_arguments']:.3f}|{m['environment_success']:.3f}|{m['http']}|{m['prompt_tokens']+m['completion_tokens']}|{m['truncations']}|"
        )
    text += [
        "",
        "Task success follows the original strict oracle, including required tool trajectory and environment checks. Reference binding separately requires a fresh final-turn get_order of the initial target and no other target read; this does not replace strict task success. Model-invalid outputs recovered by application fallback remain in the all-attempted denominator. `analysis.json` also reports valid-output subset counts; excluding invalid outputs can bias comparisons, so it is secondary.",
        "",
        "| Case | M0 | M1 | M2 |",
        "|---|---|---|---|",
    ]
    text += [f"|{case}|{v['M0']}|{v['M1']}|{v['M2']}|" for case, v in comparison.items()]
    text += [
        "",
        "## Usage, latency and reliability",
        "",
        f"Total including probe: {total['http_attempts']} HTTP attempts; {total['reported_tokens']:,} reported tokens; {total['accounted_tokens']:,} conservatively accounted tokens; peak-price estimate US${total['estimated_usd']:.6f}. Unknown usage requests: {total['unknown_usage_requests']}. All calls share the same350HTTP/300,000token/US$3 ledger; no retry loops. HTTP failures: {summary['http_failures']}; uncertain pending: {summary['pending']}. Total HTTP latency {summary['total_http_latency_ms']/1000:.3f}s.",
        "",
        "| Mode | Prompt tokens | Completion tokens | Mean task ms | P95 task ms | Mean HTTP ms | P95 HTTP ms | Invalid groups |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for mode, m in metrics.items():
        text.append(
            f"|{mode}|{m['prompt_tokens']}|{m['completion_tokens']}|{m['mean_latency_ms']:.1f}|{m['p95_latency_ms']:.1f}|{m['http_mean_ms']:.1f}|{m['http_p95_ms']:.1f}|{m['invalid_output_groups']}|"
        )
    text += [
        "",
        "Errors by request stage (raw public completions retained in local request ledger, hidden reasoning excluded):",
        "",
        "```json",
        json.dumps(errors, ensure_ascii=False, indent=2),
        "```",
        "",
        "No output-cap or JSON-repair change is introduced between arms. Truncation differences are stochastic observations, not a separately measured repair gain. Missing-tool and argument errors are retained in the original scores and executor events; failed task reasons remain in results.json. A correct entity does not guarantee Planner selection or task success.",
        "",
        "## Reproduction and limits",
        "",
        "Run configuration contains application/Prompt/data/harness hashes, effective settings fingerprints, endpoint, model, clock, limits and pricing source. Completed HTTP responses replay from the checkpoint, never by sending another request; PENDING uncertainty stops execution. Reproduction against the live API requires a fresh run directory and new budget authorization, and cannot guarantee identical outputs. The source must match the frozen P2 commit; QC source cannot resume this original-source run.",
        "",
        "Original seven are known development checks, not an independent generalization set. M3 and real QC C0/C1 are NOT_RUN. No simulated results substitute for real arms. This small experiment does not establish universal accuracy, causal JSON-repair gains, production authentication or long-window M2 superiority (the selected seven fit recent history).",
        "",
        "Cost uses published peak cache-miss input$0.30/M and output$1.20/M without discounts: https://api-docs.deepseek.com/quick_start/pricing/ . This is an estimate, not an invoice. API alias/backend and response randomness can change.",
    ]
    text += [
        "",
        "## Interrupted scope",
        "",
        "Only seven complete case triples were obtained: one normal control plus six of the original seven references. The third-order changed-state triple and both remaining controls are NOT_RUN (the M1 first request was attempted but has no durable response). Thus the planned ten triples / three normal controls are not complete; QA quality remains PARTIAL. The per-mode task denominators above contain completed groups, including model-invalid outputs recovered by fallback; the uncertain additional M1 group is excluded from paired scoring and retained separately as infrastructure ERROR/UNSCORABLE.",
        "",
        f"The uncertain attempt is a ConnectError, not a model timeout or task failure. Conservatively reserved unknown usage: {total['accounted_tokens']-total['reported_tokens']} tokens. Provider-reported usage is not proof of the unsettled request's bill. No request replay, replacement run or extra real QC requests was issued after this stop. Measured HTTP latency excludes the uncertain attempt because its failure path did not persist elapsed time; that latency is NOT_RECORDED. Three truncations remain (Planner M0/M1 and Judge M0), independently of strict task outcomes. No generalized JSON repair benefit or M2-over-M1 gain is established.",
    ]
    (QUALITY / "P2-QA_REAL_LLM_REPORT.md").write_bytes(("\n".join(text) + "\n").encode())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
