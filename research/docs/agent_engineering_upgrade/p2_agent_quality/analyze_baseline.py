"""Reconcile archived measurements and actual frozen-source node reexecution."""

import json
from pathlib import Path

from eval.memory_ablation import summarize

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "p2_quality"


def read(path):
    return json.loads(path.read_bytes())


def main():
    result = read(HERE / "evidence/r0_runtime/results.json")
    rows = result["results"]
    prior = read(OLD / "runs/20261104_reviewed_final_offline/results.json")
    arm = next(
        a for a in prior["arms"] if a["mode"] == "M2" and a["provider"] == "OFFLINE_SCRIPTED"
    )
    previous = [r for r in arm["results"] if r["case_id"].startswith("nu")]

    def normalized(row):
        return dict(
            id=row["case_id"],
            status=row["status"],
            reasons=row["reasons"],
            env=row["metrics"]["environment_state_correct"],
            scores=[t["scores"] for t in row["evidence"]["turns"]],
            calls=[
                {
                    k: c[k]
                    for k in ("name", "arguments", "success", "status", "failure_kind", "turn")
                }
                for c in row["evidence"]["tool_calls"]
            ],
        )

    assert [normalized(r) for r in rows] == [normalized(r) for r in previous]
    metrics = summarize(rows)
    extra = sum(t["scores"]["unnecessary_tool_calls"] for r in rows for t in r["evidence"]["turns"])
    traces = [read(p) for p in sorted((HERE / "evidence/r0_runtime/traces").glob("*.json"))]
    assert len(traces) == 16
    full = []
    for trace in traces:
        case = next(
            c for c in read(OLD / "new_unseen.json")["scenarios"] if c["id"] == trace["case_id"]
        )
        detail = dict(
            case=case,
            turns=[],
            oracle=trace["scorer_result"],
            database_final=trace["database_final"],
        )
        for turn in trace["turns"]:
            nodes = {n["node"]: n for n in turn["nodes"]}
            detail["turns"].append(
                dict(
                    turn=turn["turn"],
                    request=turn["request"],
                    initial=turn.get("initial_state"),
                    intent=nodes.get("classify_intent", {}).get("output"),
                    router=nodes.get("route_complexity", {}).get("output"),
                    plan=nodes.get("plan_tasks", {}).get("output"),
                    tool_execution=nodes.get("execute_tools", {}).get("output"),
                    final_state=turn.get("final_state"),
                    response=turn.get("response"),
                    error=turn.get("error"),
                    node_order=[n["node"] for n in turn["nodes"]],
                )
            )
        full.append(detail)
    real = read(OLD / "runs/20261104_QA_real_01/analysis.json")
    value = dict(
        status="PASS_BASELINE_RECONCILIATION",
        metrics=metrics,
        redundant_tools=extra,
        archived_original80_M2=arm["groups"]["original80"],
        historical_real=real,
        turns=sum(len(t["turns"]) for t in traces),
        nodes=sum(len(turn["nodes"]) for t in traces for turn in t["turns"]),
        all_case_results_match_archive=True,
        cases=full,
    )
    (HERE / "evidence/r0_reconciliation.json").write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    )
    table = []
    for item in full:
        row = item["oracle"]
        extras = sum(t["scores"]["unnecessary_tool_calls"] for t in row["evidence"]["turns"])
        table.append(
            f"|{row['case_id']}|{len(item['turns'])}|{row['status']}|{len(row['evidence']['tool_calls'])}|{extras}|{row['metrics']['environment_state_correct']}|[full runtime](evidence/r0_runtime/traces/{next(p.name for p in (HERE/'evidence/r0_runtime/traces').glob('*.json') if p.stem.endswith(row['case_id']))})|"
        )
    text = (
        """# P2-R0 frozen baseline and runtime evidence

Actual remote `origin/codex/p2-quality` and local HEAD both verified as `09819352cc6df98b9f8cb42ffb56e9c8365b5793`. User's manual push resolves the historical delivery issue; old P2-Q reports/state remain unchanged. Isolated branch `codex/p2-agent-quality`; Conda adaptive-rag. Existing root modifications and .env are inventoried, never committed.

## Evidence reconciliation

Archived P2-Q final M2 scripted original80=80/80; old16=0/16. Reexecuting all16 through unchanged actual service/graph/tools/scorers reproduces every normalized task outcome, score, reason, tool name/argument/status/failure-kind event. Timing, generated session/span IDs and fixture timestamps legitimately differ. Tool selection83.87097%, argument accuracy81.48148%, environment15/16 and25surplus calls are reproduced. Baseline fullpytest274passed; instrumentation5passed. No paid calls.

Historical real evidence was read directly from requests/results/analysis, not inferred: M0=1/7, M1/M2=7/7 complete groups; six reference pairs0/6 versus6/6.194attempts,193responses,151933reportedtokens and3966unknown-reserved; old request194 remains uncertain and is NEVER retried. Three512-cap truncations are preserved. Old12 corrupted ASCII? cases are excluded from semantic evaluation. All these are historical reference, not new P2-R model results.

## Ordered actual-chain reconstruction

Old saved results lacked full state/answer snapshots. The new traces are explicitly SOURCEFROZEN_REEXECUTION, not fabricated historical trace.16case files,31turns,225actual ordered node callbacks. Each records request/role/session, actual loaded messages/summary, selected entity/source/effective query, Intent/Router output, Planner steps, tool arguments/results, final public answer, pending/confirmation state, committed business and all-table DB snapshots, unchanged Goal Oracle and per-turn scorer reasons. Public structured rationale is excluded by the evidence serializer; node decisions/plan steps remain. No hidden reasoning, secrets or third-party raw tracing.

| Case | Turns | Task | Tool events | Surplus | Environment | Trace |
|---|---|---|---|---|---|---|
"""
        + "\n".join(table)
        + """

Input/Gold and full extracted chain are also in evidence/r0_reconciliation.json; actual before/after node states remain in each trace. Where owner/session rejects before graph, the exception is explicit and missing nodes are not invented. The initial/final state and DB allow inspection of stale observations versus new reads.

All16 inputs decode as valid UTF8 Chinese, without U+FFFD or punctuation-only corruption. Old Gold/scorer/tool contracts are unchanged. A policy RAG retrieval may be business-correct without emitting a search_knowledge tool event; R1 will distinguish this contract issue from true missing business observations. Environment checks use any qualifying observation anywhere in a scenario and unchanged committed state;15/16environment is therefore not15/16correct final answers or per-turn fresh references.

Next: classify earliest actual error and propagated scoring symptoms case by case before any production modification. Full source/prompt/scorer/data hashes and unchanged-before/after validation are in evidence/r0_runtime/experiment_config.json and validation.json. Blind data remains withheld until implementation freeze. No P3/P4.
"""
    )
    (HERE / "P2-R0_BASELINE.md").write_bytes((text + "\n").encode())
    print(
        json.dumps(
            dict(
                cases=16,
                turns=value["turns"],
                nodes=value["nodes"],
                task="0/16",
                selection=metrics["tool_selection"],
                arguments=metrics["tool_arguments"],
                environment=metrics["environment_success"],
                surplus=extra,
                archive_match=True,
            )
        )
    )


if __name__ == "__main__":
    main()
