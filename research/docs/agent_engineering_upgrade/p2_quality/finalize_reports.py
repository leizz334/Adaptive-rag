"""Evidence-derived QC/QD reports; does not execute models or modify application code."""

import json
from pathlib import Path

from research.docs.agent_engineering_upgrade.p2_quality.analyze_offline import analyze

HERE = Path(__file__).resolve().parent


def write(name, text):
    (HERE / name).write_bytes((text + "\n").encode())


def main():
    runs = {
        name: analyze(HERE / "runs" / name / "results.json")
        for name in [
            "20261104_C0_offline",
            "20261104_C0_unseen",
            "20261104_final_offline",
            "20261104_reviewed_final_offline",
        ]
    }
    (HERE / "attribution.json").write_bytes(
        (json.dumps(runs, ensure_ascii=False, indent=2) + "\n").encode()
    )

    def arm(run, mode="M2"):
        return next(
            a
            for a in runs[run]["arms"]
            if a["mode"] == mode and a["provider"] == "OFFLINE_SCRIPTED"
        )["groups"]

    before = arm("20261104_C0_offline")
    after = arm("20261104_reviewed_final_offline")
    rows = []
    for group in ("original80", "owner7", "long_window", "diagnostic12"):
        b, a = before[group], after[group]
        rows.append(
            f"|{group}|{b['passed']}/{b['cases']} → {a['passed']}/{a['cases']}|{b['tool_calls']} → {a['tool_calls']}|{b['scorer_redundant_tool_calls']} → {a['scorer_redundant_tool_calls']}|{b['wrong_arguments']} → {a['wrong_arguments']}|{b['environment_success']:.3f} → {a['environment_success']:.3f}|{b['mean_latency_ms']:.1f} → {a['mean_latency_ms']:.1f}|{b['p95_latency_ms']:.1f} → {a['p95_latency_ms']:.1f}|"
        )
    qc = (
        """# P2-QC Planner/Fallback control

OFFLINE control only. Real C0/C1 = NOT_RUN: the global paid ledger has an uncertain ConnectError at request194 and paid work was stopped. Same M2 Memory implementation, frozen data/Gold/scorers, fixture and scripted provider across C0/C1. No Memory module was changed.

## Confirmed paths and minimal repair

1. Repository owner/not-found rejection is an InvalidRequestError. Tool.run records business_rejected. Previously execute_with_fallback treated it as a transient error, querying knowledge and later retrying get_order through track_shipment fallback. The user goal was only order status. Neither policy retrieval nor a second denied lookup supplies new authoritative evidence. Deterministic argument/business/permission rejection now propagates; transient ToolExecutionError retains read fallback and fresh next-turn reads. No cache was introduced. Necessary initial repository Owner validation remains.
2. The order_tracking skill listed both get_order and track_shipment for every order inquiry. get_order already returns order status and timestamps. Long-window M2 correctly restored the entity and read the new delivered state, but shipment reads violated the unchanged, justified status-only tool contract. A complete narrow order-header goal now selects the needed skill subset in both offline fallback and real-shaped Planner catalog/sanitization. Unknown language/additional goals preserve shipment capability. The prompt describes skills as candidate capabilities rather than compulsory complete tool lists.

Three production files changed: app/agents/nodes/executor.py, app/agents/nodes/planner.py, app/prompts/planner.py. No ownership, HITL, business state, idempotency, summary, Gold or scorer changes.

## Fixed-M2 outcome

| Group | Task success C0→C1 | Tool events | Scorer redundant | Argument-mismatch turns | Environment | Mean task ms | P95 task ms |
|---|---|---|---|---|---|---|---|
"""
        + "\n".join(rows)
        + """

Argument-mismatch turns include missing required calls under the original oracle, not just executed wrong IDs. Tool events include idempotent replay observations. Full raw cases, per-mode token-bound estimates and failures are retained in runs and attribution.json. No offline fixture token estimate is billed model usage.

Owner seven: foreign_order; owner_ORD10001_other; owner_ORD10001_anonymous; owner_ORD10002_other; owner_ORD10002_anonymous; owner_ORD10003_other; owner_ORD10003_anonymous. Each changes FAIL→PASS, 5→1 events, while the initial owned-order query still rejects access and no protected output is disclosed. The original scorer counted one redundant get_order per case; the other eliminated calls were unnecessary for this status-only goal but must not be relabeled as seven additional oracle violations.

Long-window M2 changes 4→2 tool events across two order turns, 2→0 surplus shipment calls, 0/1→1/1 strict task success. Its environment success was already1/1 in C0; this is a Planner gain enabled by existing summary recovery, not a new Memory fix. M0/M1 still fail after the entity leaves their window.

The full80 has no new task failures or observed hard safety violations relative to original P2. 177→99 tool events and 2.2125→1.2375 events/task. The old12 remains3/12; those nine corrupt-input failures were not repaired or hidden. Latencies are noisy local offline observations (other checks ran concurrently); no causal speedup claim follows.

## Independent review and retained regression

Initial broad keyword pruning was rejected by an independent reviewer: a transport-history request containing 状态 lost necessary shipment capability. Generic ORD24680 repro observed RED1/9PASS, then GREEN; real-shaped and fallback plans retain the transport-history tool. Regrade passed five focused probes. Final logic uses positive recognition of a complete order-only request rather than a blacklist of logistics synonyms. Unknown requests retain tools, which reduces strict trajectory coverage.

Initial frozen unseen evaluation (before this reviewer repair) was8/16 at M2; final post-review regression is0/16, with25 redundant calls and5 argument-mismatch turns. Original P2 C0 was0/16. These failures expose the remaining coverage/Planner problem and are not tuned away. No unseen inputs were used to author the reviewer fix. The initial output remains in20261104_final_offline; final output is20261104_reviewed_final_offline. The latter is regression, not a fresh blind sample. New unseen Environment success is15/16; Tool selection0.8387; argument accuracy0.8148. Real generalization for this set is NOT_RUN.

Validation: initial5RED/4PASS; targetedGREEN10; reviewerRED1/9PASS; reviewedGREEN11; final274pytestPASS; independent regradePASS. Session/Owner isolation, HITL, idempotency, JSON/exception handling and tracing tests remain in the unchanged full suite. No score contract was changed. The strict status-only exclusion is justified by tool outputs, but unknown-language overcalling remains unresolved.
"""
    )
    write("P2-QC_PLANNER_REPORT.md", qc)
    matrix = []
    for label, run in [
        ("Original P2 / Memory-only (identical source)", "20261104_C0_offline"),
        ("Planner-only / Combined (identical source)", "20261104_reviewed_final_offline"),
    ]:
        for mode in ("M0", "M1", "M2"):
            values = arm(run, mode)
            new = (
                arm("20261104_C0_unseen", mode)["new_unseen"]
                if run.endswith("C0_offline")
                else values["new_unseen"]
            )
            matrix.append(
                f"|{label}|{mode}|{values['original80']['passed']}/80|{values['original7']['passed']}/7|{values['diagnostic12']['passed']}/12|{values['long_window']['passed']}/1|{new['passed']}/16|"
            )
    final = (
        """# P2-Q final report

Phase status: **PARTIAL_PASS**. Engineering checks pass; real paired scope and quality/generalization remain PARTIAL. Original P1/P2 PARTIAL_PASS and historical real PARTIAL records are unchanged. No P3/P4 started.

QA: official DeepSeekProvider connected, requested/observed deepseek-flash. Seven complete triples (one control and six original reference cases): M0=1/7, M1=7/7, M2=7/7. Reference binding0/6 versus6/6 and6/6. This verifies existing recent-history benefit on completed known cases, not a new Memory-code gain or M2 superiority. The final original reference and two normal controls have no complete real triple and are NOT_RUN/UNSCORABLE. The planned three normal controls were not completed.

There were194HTTP attempts,193durable200responses,151,933provider-reported tokens and3,966tokens reserved for one uncertain ConnectError (155,899accounted). Peak-price estimatedUS$0.0785172 including reservation, not a settled invoice. Limits350/300,000/US$3 were respected. No paid retry or subsequent real QC run occurred. HTTP failures0, transport ConnectError1, timeouts0; uncertain billing/latency unresolved. Successful-request latency331.454s excludes the uncertain attempt. M0 task mean/P95=16.247/24.584s; M1=16.588/19.329s; M2=15.825/19.267s.

Three structured-output truncations remain: Planner M1, Planner M0, Judge M0 (all512tokencaps). Post-hoc production-schema parsing checked192completions and found only these three invalid outputs. Fallback-recovered tasks retain their errors. No reliability caps or JSON repair changed between real modes; differences do not prove Memory improves JSON reliability. Unchanged driver metadata incorrectly defaults model_evaluation toNOT_RUN; model_provenance.json corrects that infrastructure label using actual HTTP records without overwriting raw payloads.

QB: all nine old heldout failures traced to literalASCII? input corruption in the original frozen commit. No missing language or node spans were fabricated. Frozen Gold and FAILs remain. Memory changes justified by those inputs: zero. New generic tests retain no-guessing, proper entity binding, freshness and assistant exclusion. Old12 are diagnostic/regression now, not an independent semantic generalization benchmark.

## Attribution with fixed remaining factors

| Source variant | Memory | Original80 | Original7 | Old diagnostic12 | Long window | New16 final regression |
|---|---|---|---|---|---|---|
"""
        + "\n".join(matrix)
        + """

The four requested labels represent two distinct implementations because no Memory patch was justified: Memory-only equals original P2; Combined equals Planner-only. Results are reused for identical source, not represented as four independent experiments. All Gold/scorers and Memory settings are fixed per comparison. Prompt change belongs exclusively to QC. QC gains cannot be credited to Memory. Existing M2 summary plus QC removes the long-window strict trajectory failure; enabling Memory alone had already restored fresh entity/state but did not pass the original trajectory.

Memory-only code improvement:0 (no patch); existing real Memory switch improves six completed reference tasks. Planner-only improvement at fixedM2: original80 73→80; owner7 0→7; long-window0→1; old12 unchanged3. Combined equals Planner-only. New16 initial blinded C0=0/16 and initial candidateM2=8/16; after the independent transport-history safety/correctness repair, final regressionM2=0/16. The candidate improvement was withdrawn rather than preserved with an overbroad tool restriction. No generalized success claim is justified. All final16failures and old9failures remain visible. The new16 are now used evaluation/regression data and must not be called unseen for future work.

## Final verification and limitations

274pytest passed. Ruff check and format check passed (212files); Mypy passed137source files. Full original80 passes underM1/M2, and all original safety/Owner/Session/HITL/idempotency/JSON/provider/local-trace/disabled-external-trace regressions pass. Observed hard safety violations0. This does not establish trusted production identity; public cross-sessionM3 remains disabled and realM3=NOT_RUN.

110historical artifacts are byte-preserved; all historical task keys except the separate newp2_quality object are unchanged; original progress is a preserved prefix;20root user files including ignored.env are hash-preserved. Frozen datasets and scorers unchanged. All recorded tool-turn scores are recomputed by verify_quality.py. Reviewed source and new dataset hashes are frozen. No credential or hidden reasoning is present in phase artifacts. No external raw tracing was enabled.

Known infrastructure defects are explicitly retained: old dataset language corruption; inherited real-driver NOT_RUN metadata corrected by sidecar; initial C0 tool-count aggregator used the wrong nesting (recomputed_metrics/attribution are authoritative); uncertain transport-attempt latency not recorded. Offline latency is descriptive and confounded by concurrent checks, not a controlled performance benchmark. API alias/randomness, small sample and stopped scope limit reproducibility.

Remaining gates: reconcile request194 with provider billing before any paid resume; complete the remaining real pairs in an authorized new frozen-source run without repeating existing requests; improve generic Context/Planner coverage using a separate development set and future independently frozen evaluation; retain all failed checks and current narrow safety constraints. No extra calls are implied or authorized beyond this phase's stopped ledger.

## Recovery / Git

Each authorized task has its own checkpoint in feature-list.json/progress.txt. See those files and git log for exact hashes. Work is isolated oncodex/p2-quality from pushedP2c45f509; ordinary push only after final remote/branch/user-file verification. The final delivery checkpoint records actual push outcome. Never resume the paid runner merely because budget remains: its PENDING row is deliberately fail-closed. STOP after P2-Q; noP3/P4.
"""
    )
    write("P2-Q_FINAL_REPORT.md", final)
    path = HERE / "P2-QB_FAILURE_ANALYSIS.md"
    addition = """
## Parent completion / new independent evaluation

The unchanged old12 were rerun: M0=2/12; M1/M2=3/12.23focused Memory/context tests passed, followed by274full tests. No Memory module was modified.16new UTF-8-checked cases were independently frozen before implementation and first executed after the initial source freeze. Initial candidateM2=8/16; original-sourceC0=0/16. An independent transport-history review repro required a conservative Planner repair; final regressionM2=0/16 and15/16Environment success. This does not repair the nine old failures or prove general reference resolution. The initial new results and final regression are separate immutable runs; no Gold or input was changed and no unseen input was used to author the reviewer repair. The new16 are no longer a fresh blind set for future work. Per-case failures/metrics are in attribution.json and the final reviewed run. QA real scope is partial; real new16=NOT_RUN.
"""
    if "## Parent completion / new independent evaluation" not in path.read_text(encoding="utf-8"):
        path.write_bytes(path.read_bytes() + addition.encode())
    print(
        json.dumps(
            dict(
                QC="PASS_OFFLINE_QUALITY_PARTIAL",
                QD="274PASS_QUALITY_PARTIAL",
                unseen_final="0/16",
                phase="PARTIAL_PASS",
            )
        )
    )


if __name__ == "__main__":
    main()
