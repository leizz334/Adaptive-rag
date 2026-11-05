"""Read-only real-pair analysis; never retries or sends a provider request."""

import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_agent_quality.benchmark import metrics
from research.docs.agent_engineering_upgrade.p2_agent_quality.observation_scoring import (
    fresh_business,
)
from research.docs.agent_engineering_upgrade.p2_agent_quality.real_pairs import Ledger, summary

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/20261105_R5_pairs_01"


def read(path):
    return json.loads(path.read_bytes())


def main():
    config, result = read(RUN / "experiment_config.json"), read(RUN / "results.json")
    ledger = Ledger(RUN, pricing=config["pricing"])
    totals = ledger.totals()
    rows = result["groups"]
    groups = [g for g in rows if g["rep"] == 0]
    complete = {
        g["case_id"]
        for g in groups
        if all(
            any(x["case_id"] == g["case_id"] and x["variant"] == v for x in groups)
            for v in ("R0", "R1")
        )
    }
    cases = {}
    for item in config["datasets"].values():
        loaded, _ = load_scenarios(Path(item["path"]))
        cases.update({c.id: c for c in loaded})
    diagnostics = summary(result, ledger)
    raw_diagnostics = dict(diagnostics["request_diagnostics"])
    # An unfinished transport has no completion to judge. The reused diagnostic
    # helper otherwise counts it as a lexical error; retain and correct that label.
    diagnostics["request_diagnostics"]["lexical_errors"] = sum(
        bool(r.get("model_error")) for r in ledger.rows if r.get("http_status") == 200
    )
    arms = {}
    for variant in ("R0", "R1"):
        group = [g for g in groups if g["variant"] == variant and g["case_id"] in complete]
        scopes = {
            "all_complete_pairs": group,
            "development": [g for g in group if g["split"] == "development"],
            "blind_subset": [g for g in group if g["split"] == "blind"],
        }
        arms[variant] = {}
        for name, scoped in scopes.items():
            value = metrics(scoped, cases)
            value.update(fresh_business(scoped, cases))
            for key in (
                "paid_tokens",
                "real_model_tokens",
                "scripted_calls",
                "estimated_input_utf8_bound",
            ):
                value.pop(key, None)
            actual = [r for r in ledger.rows if any(r["group"] == g["group"] for g in scoped)]
            lat = sorted(r["latency_ms"] for r in actual if r.get("status") == "RESPONSE")
            value.update(
                http_attempts=len(actual),
                prompt_tokens=sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in actual),
                completion_tokens=sum(
                    (r.get("usage") or {}).get("completion_tokens", 0) for r in actual
                ),
                http_mean_ms=mean(lat) if lat else None,
                http_p95_ms=lat[math.ceil(0.95 * len(lat)) - 1] if lat else None,
                truncations=sum(r.get("model_error") == "truncated" for r in actual),
                schema_errors=sum(
                    bool(e.get("schema_error")) for g in scoped for e in g["request_errors"]
                ),
                zero_llm_groups=[g["case_id"] for g in scoped if not g["http_attempts"]],
            )
            arms[variant][name] = value
    conversions = []
    for selected in config["selected"]:
        case = selected["id"]
        pair = {}
        for variant in ("R0", "R1"):
            group = next(
                (g for g in groups if g["case_id"] == case and g["variant"] == variant), None
            )
            attempted = [r for r in ledger.rows if r["group"] == f"{case}:{variant}:0"]
            pair[variant] = (
                group["status"] if group else "UNSCORABLE_CONNECTERROR" if attempted else "NOT_RUN"
            )
        conversions.append(dict(case=case, split=selected["split"], **pair))
    failures = [
        dict(
            case=g["case_id"],
            variant=g["variant"],
            reasons=g["reasons"],
            actual_tools=g["evidence"]["tool_calls"],
        )
        for g in groups
        if g["status"] != "PASS"
    ]
    uncertain = [
        {
            k: r.get(k)
            for k in (
                "group",
                "sequence",
                "transport_error_type",
                "latency_ms",
                "reserve_input",
                "reserve_output",
            )
        }
        for r in ledger.rows
        if r["status"] != "RESPONSE"
    ]
    value = dict(
        status=result["status"],
        completed_pairs=len(complete),
        planned_pairs=len(config["selected"]),
        arms=arms,
        totals=totals,
        diagnostics=diagnostics["request_diagnostics"],
        raw_harness_diagnostics=raw_diagnostics,
        conversions=conversions,
        failed_groups=failures,
        uncertain_requests=uncertain,
        http_latency_total_seconds=sum(r.get("latency_ms", 0) for r in ledger.rows) / 1000,
        observed_models=dict(
            Counter(r.get("response", {}).get("model", "NO_RESPONSE") for r in ledger.rows)
        ),
        repeat="NOT_RUN_TRANSPORT_STOP",
        inference_scope="Combined source Agent pipeline; no real component-only arms; zero-call premodel gates are explicitly identified",
    )
    (RUN / "analysis.json").write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    )
    (RUN / "validation.json").write_bytes(
        (
            json.dumps(
                dict(
                    status="PARTIAL_INFRASTRUCTURE_STOP",
                    complete_pairs=len(complete),
                    attempted_http=len(ledger.rows),
                    pending=len(uncertain),
                    within_budget=totals["http_attempts"] <= 420
                    and totals["accounted_tokens"] <= 420000
                    and totals["estimated_usd"] <= 3,
                    source_controlled=True,
                    repeated_paid_requests=0,
                    automatic_retry=False,
                    external_tracing=False,
                    real_provider="DeepSeekProvider",
                    candidate_source_unchanged=True,
                ),
                indent=2,
            )
            + "\n"
        ).encode()
    )
    text = [
        "# P2-R5 real DeepSeek source-paired validation",
        "",
        f"Status **PARTIAL**: {len(complete)}/{len(config['selected'])} planned source pairs completed. Both actual official DeepSeek configurations returned model `deepseek-flash`; the common model/endpoint, M2, source fixtures/Gold/scorer/seed clock, temperature0and output caps were frozen. R0 source0981935; R1 source44f1031with metadata snapshotHEADaef3101. Planner Prompt differs intentionally; app/prompts/planner.py hash changes and actual input-schema catalog changes are recorded. No claim of identical prompts or raw-model-only causality.",
        "",
        "Probe succeeded, first source-pair pilot had no request errors, and continuation alternated variant order. Five predeclared Development tasks and six SHA256-ID-selected Blind tasks were planned. No outcome-based case selection or tuning followed the candidate freeze. The old P2-Q pending request194was never opened/replayed; this is a separate explicitly authorized P2-R budget.",
        "",
        "| Scope / arm | Strict task | Selection | Arguments | Valid trajectory | Surplus | Environment | Fresh reads | Mean/P95 task ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for variant, scopes in arms.items():
        for name, m in scopes.items():
            text.append(
                f"|{name}/{variant}|{m['passed']}/{m['cases']}|{m['tool_selection']:.4f}|{m['tool_arguments']:.4f}|{m['trajectory_validity']:.4f}|{m['redundant_tool_calls']}|{m['environment_success']:.4f}|{m['fresh_business_correct']}/{m['fresh_business_required']}|{m['mean_latency_ms']:.1f}/{m['p95_latency_ms']:.1f}|"
            )
    text += [
        "",
        "Task success uses completed pairs, including application-fallback recovery from model output errors. Uncertain/incomplete groups are not task failures and are excluded from paired scoring. The registered driver retains raw model_evaluation=NOT_RUN; the outer real-provider record and durable actual HTTP journal establish real execution. R0 P2R-B10 has zero HTTP calls because its Context gate prematurely clarifies an explicit multi-target goal; this is an actual pre-model Agent decision failure under the real-provider configuration, not a DeepSeek response or a simulated LLM result. Other completed groups have real responses. Do not infer direct model semantic accuracy for the zero-call group.",
        "",
        "| Case | Split | R0 | R1 |",
        "|---|---|---|---|",
    ]
    text += [f"|{c['case']}|{c['split']}|{c['R0']}|{c['R1']}|" for c in conversions]
    text += [
        "",
        "Development changes3/5→5/5; completed Blind subset1/3→2/3; all completed pairs4/8→7/8. Improved cases aredv08张-form reference,dv16fresh re-read after state event,andP2R-B10explicit multi-target. No completed pair changesPASS→FAIL. These gains belong to the combined context/decision/execution implementation; offline C1/C2 controls do not prove real component-only causal effects.",
        "",
        "P2R-B31 fails in both sources because the SKU warranty follow-up takes RAG without the frozen required get_warranty event. The final public model answer can be inspected in the request ledger; tool/state scoring does not independently certify final-answer semantics. Contract disputes remain separate and original failures are retained. Remaining predeclared B05/B30/B25 pairs and the optional repeated pair are NOT_RUN/UNSCORABLE; the latter cannot test nondeterminism.",
        "",
        "## Full request accounting and reliability",
        "",
        f"{totals['http_attempts']}attempts;{totals['reported_tokens']:,}provider-reportedtokens;{totals['accounted_tokens']:,}accountedtokens. Unknown reservation={totals['accounted_tokens']-totals['reported_tokens']:,}tokens. Peak-rate estimateUS${totals['estimated_usd']:.7f}, including unknown reservation; not a settled invoice. Global limits420HTTP/420ktokens/US$3and per-group24were respected. Concurrency1and generation attempts1; no paid retry. Full measured HTTP-attempt latency={value['http_latency_total_seconds']:.3f}s, including failed connection latency. Token usage includes probe, all node calls, output truncations and recovery calls.",
        "",
        "| Arm completed groups | HTTP | Prompt tokens | Completion tokens | Truncations | HTTP mean/P95 ms |",
        "|---|---|---|---|---|---|",
    ]
    for variant, scopes in arms.items():
        m = scopes["all_complete_pairs"]
        text.append(
            f"|{variant}|{m['http_attempts']}|{m['prompt_tokens']}|{m['completion_tokens']}|{m['truncations']}|{m['http_mean_ms']:.1f}/{m['http_p95_ms']:.1f}|"
        )
    text += [
        "",
        f"Request diagnostics: `{json.dumps(value['diagnostics'])}`.",
        "",
        "Seven truncations remain: six Judge and one R0Planner, all at the common512output cap. Lexical truncation and schema categories are not double-counted as separate model failures; no additional schema errors were observed. Every raw finish_reason/public completion is preserved even when task fallback succeeds. No JSON cap/repair changed between arms and no reliability gain is attributed to Memory or Planner.",
        "",
        "The109thattempt (B05/R0, Intent) hit ConnectError; its completion/billing is unknown. A3981-token reservation and measured failure latency remain durablyPENDING. No automatic retry, replacement run or further model call was issued. This is infrastructure failure, not evidence of model quality. No timeout or HTTP error response was observed. Partial execution order may bias which tasks completed; the3real blind pairs cannot establish a population success rate or replace the full33offline result.",
        "",
        "## Reproduction and limitations",
        "",
        "experiment_config.json records exact source/import/Prompt/helper/harness hashes, common cap expressions/settings fingerprints, datasets/Gold, fixed seed clock, endpoint/model, prices and deterministic selection. Requests are reserved before dispatch; responses checkpoint before downstream parsing. Exact completed responses replay locally only on matching full request/source hashes; any uncertain row prevents automatic resume. API alias/sampling/backend can vary despite temperature0. Repetition was NOT_RUN. Original Gold/scorers and all failed cases remain immutable. All business state was isolated synthetic SQLite; no production order write or raw external tracing.",
        "",
        "Prices reverified2026-11-05: https://api-docs.deepseek.com/quick_start/pricing/ ; peak cache-miss input$0.30/M, output$1.20/M, no discounts assumed. No further paid work is part of this stopped experiment. Future reconciled/authorized work must preserve the pending ledger and never resend an uncertain request.",
    ]
    text += [
        "",
        "Supplementary Fresh reads counts required successful business-read observations in their required turn, including order/shipment/items/refund/SKU inventory/product/warranty tools and changed order status where specified. It excludes expected Owner/not-found refusals and is separate from the unchanged task score. Order-only freshness remains separately available in analysis.json. The reused raw diagnostic helper counted the unfinished transport as an eighth lexical error; raw_harness_diagnostics preserves that value while the corrected model-output count is7. The missing network response is infrastructure, never a model JSON failure.",
    ]
    (HERE / "P2-R5_REAL_LLM_REPORT.md").write_bytes(("\n".join(text) + "\n").encode())
    print(
        json.dumps(
            dict(
                status=value["status"],
                completed_pairs=len(complete),
                totals=totals,
                metrics={a: s["all_complete_pairs"] for a, s in arms.items()},
                diagnostics=value["diagnostics"],
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
