# P2-QC Planner/Fallback control

OFFLINE control only. Real C0/C1 = NOT_RUN: the global paid ledger has an uncertain ConnectError at request194 and paid work was stopped. Same M2 Memory implementation, frozen data/Gold/scorers, fixture and scripted provider across C0/C1. No Memory module was changed.

## Confirmed paths and minimal repair

1. Repository owner/not-found rejection is an InvalidRequestError. Tool.run records business_rejected. Previously execute_with_fallback treated it as a transient error, querying knowledge and later retrying get_order through track_shipment fallback. The user goal was only order status. Neither policy retrieval nor a second denied lookup supplies new authoritative evidence. Deterministic argument/business/permission rejection now propagates; transient ToolExecutionError retains read fallback and fresh next-turn reads. No cache was introduced. Necessary initial repository Owner validation remains.
2. The order_tracking skill listed both get_order and track_shipment for every order inquiry. get_order already returns order status and timestamps. Long-window M2 correctly restored the entity and read the new delivered state, but shipment reads violated the unchanged, justified status-only tool contract. A complete narrow order-header goal now selects the needed skill subset in both offline fallback and real-shaped Planner catalog/sanitization. Unknown language/additional goals preserve shipment capability. The prompt describes skills as candidate capabilities rather than compulsory complete tool lists.

Three production files changed: app/agents/nodes/executor.py, app/agents/nodes/planner.py, app/prompts/planner.py. No ownership, HITL, business state, idempotency, summary, Gold or scorer changes.

## Fixed-M2 outcome

| Group | Task success C0→C1 | Tool events | Scorer redundant | Argument-mismatch turns | Environment | Mean task ms | P95 task ms |
|---|---|---|---|---|---|---|---|
|original80|73/80 → 80/80|177 → 99|7 → 0|0 → 0|1.000 → 1.000|266.1 → 279.4|444.5 → 472.9|
|owner7|0/7 → 7/7|35 → 7|7 → 0|0 → 0|1.000 → 1.000|264.3 → 246.7|444.5 → 264.9|
|long_window|0/1 → 1/1|4 → 2|2 → 0|0 → 0|1.000 → 1.000|444.2 → 383.9|444.2 → 383.9|
|diagnostic12|3/12 → 3/12|26 → 26|0 → 0|9 → 9|0.750 → 0.750|290.3 → 284.0|492.8 → 461.1|

Argument-mismatch turns include missing required calls under the original oracle, not just executed wrong IDs. Tool events include idempotent replay observations. Full raw cases, per-mode token-bound estimates and failures are retained in runs and attribution.json. No offline fixture token estimate is billed model usage.

Owner seven: foreign_order; owner_ORD10001_other; owner_ORD10001_anonymous; owner_ORD10002_other; owner_ORD10002_anonymous; owner_ORD10003_other; owner_ORD10003_anonymous. Each changes FAIL→PASS, 5→1 events, while the initial owned-order query still rejects access and no protected output is disclosed. The original scorer counted one redundant get_order per case; the other eliminated calls were unnecessary for this status-only goal but must not be relabeled as seven additional oracle violations.

Long-window M2 changes 4→2 tool events across two order turns, 2→0 surplus shipment calls, 0/1→1/1 strict task success. Its environment success was already1/1 in C0; this is a Planner gain enabled by existing summary recovery, not a new Memory fix. M0/M1 still fail after the entity leaves their window.

The full80 has no new task failures or observed hard safety violations relative to original P2. 177→99 tool events and 2.2125→1.2375 events/task. The old12 remains3/12; those nine corrupt-input failures were not repaired or hidden. Latencies are noisy local offline observations (other checks ran concurrently); no causal speedup claim follows.

## Independent review and retained regression

Initial broad keyword pruning was rejected by an independent reviewer: a transport-history request containing 状态 lost necessary shipment capability. Generic ORD24680 repro observed RED1/9PASS, then GREEN; real-shaped and fallback plans retain the transport-history tool. Regrade passed five focused probes. Final logic uses positive recognition of a complete order-only request rather than a blacklist of logistics synonyms. Unknown requests retain tools, which reduces strict trajectory coverage.

Initial frozen unseen evaluation (before this reviewer repair) was8/16 at M2; final post-review regression is0/16, with25 redundant calls and5 argument-mismatch turns. Original P2 C0 was0/16. These failures expose the remaining coverage/Planner problem and are not tuned away. No unseen inputs were used to author the reviewer fix. The initial output remains in20261104_final_offline; final output is20261104_reviewed_final_offline. The latter is regression, not a fresh blind sample. New unseen Environment success is15/16; Tool selection0.8387; argument accuracy0.8148. Real generalization for this set is NOT_RUN.

Validation: initial5RED/4PASS; targetedGREEN10; reviewerRED1/9PASS; reviewedGREEN11; final274pytestPASS; independent regradePASS. Session/Owner isolation, HITL, idempotency, JSON/exception handling and tracing tests remain in the unchanged full suite. No score contract was changed. The strict status-only exclusion is justified by tool outputs, but unknown-language overcalling remains unresolved.

