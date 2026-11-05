# P2-R0 frozen baseline and runtime evidence

Actual remote `origin/codex/p2-quality` and local HEAD both verified as `09819352cc6df98b9f8cb42ffb56e9c8365b5793`. User's manual push resolves the historical delivery issue; old P2-Q reports/state remain unchanged. Isolated branch `codex/p2-agent-quality`; Conda adaptive-rag. Existing root modifications and .env are inventoried, never committed.

## Evidence reconciliation

Archived P2-Q final M2 scripted original80=80/80; old16=0/16. Reexecuting all16 through unchanged actual service/graph/tools/scorers reproduces every normalized task outcome, score, reason, tool name/argument/status/failure-kind event. Timing, generated session/span IDs and fixture timestamps legitimately differ. Tool selection83.87097%, argument accuracy81.48148%, environment15/16 and25surplus calls are reproduced. Baseline fullpytest274passed; instrumentation5passed. No paid calls.

Historical real evidence was read directly from requests/results/analysis, not inferred: M0=1/7, M1/M2=7/7 complete groups; six reference pairs0/6 versus6/6.194attempts,193responses,151933reportedtokens and3966unknown-reserved; old request194 remains uncertain and is NEVER retried. Three512-cap truncations are preserved. Old12 corrupted ASCII? cases are excluded from semantic evaluation. All these are historical reference, not new P2-R model results.

## Ordered actual-chain reconstruction

Old saved results lacked full state/answer snapshots. The new traces are explicitly SOURCEFROZEN_REEXECUTION, not fabricated historical trace.16case files,31turns,225actual ordered node callbacks. Each records request/role/session, actual loaded messages/summary, selected entity/source/effective query, Intent/Router output, Planner steps, tool arguments/results, final public answer, pending/confirmation state, committed business and all-table DB snapshots, unchanged Goal Oracle and per-turn scorer reasons. Public structured rationale is excluded by the evidence serializer; node decisions/plan steps remain. No hidden reasoning, secrets or third-party raw tracing.

| Case | Turns | Task | Tool events | Surplus | Environment | Trace |
|---|---|---|---|---|---|---|
|nu01|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/000_nu01.json)|
|nu02|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/001_nu02.json)|
|nu03|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/002_nu03.json)|
|nu04|3|FAIL|6|3|1.0|[full runtime](evidence/r0_runtime/traces/003_nu04.json)|
|nu05|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/004_nu05.json)|
|nu06|2|FAIL|0|0|1.0|[full runtime](evidence/r0_runtime/traces/005_nu06.json)|
|nu07|1|FAIL|2|2|1.0|[full runtime](evidence/r0_runtime/traces/006_nu07.json)|
|nu08|2|FAIL|4|2|0.0|[full runtime](evidence/r0_runtime/traces/007_nu08.json)|
|nu09|2|FAIL|2|1|1.0|[full runtime](evidence/r0_runtime/traces/008_nu09.json)|
|nu10|2|FAIL|2|1|1.0|[full runtime](evidence/r0_runtime/traces/009_nu10.json)|
|nu11|1|FAIL|2|1|1.0|[full runtime](evidence/r0_runtime/traces/010_nu11.json)|
|nu12|1|FAIL|0|0|1.0|[full runtime](evidence/r0_runtime/traces/011_nu12.json)|
|nu13|2|FAIL|2|1|1.0|[full runtime](evidence/r0_runtime/traces/012_nu13.json)|
|nu14|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/013_nu14.json)|
|nu15|2|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/014_nu15.json)|
|nu16|3|FAIL|4|2|1.0|[full runtime](evidence/r0_runtime/traces/015_nu16.json)|

Input/Gold and full extracted chain are also in evidence/r0_reconciliation.json; actual before/after node states remain in each trace. Where owner/session rejects before graph, the exception is explicit and missing nodes are not invented. The initial/final state and DB allow inspection of stale observations versus new reads.

All16 inputs decode as valid UTF8 Chinese, without U+FFFD or punctuation-only corruption. Old Gold/scorer/tool contracts are unchanged. A policy RAG retrieval may be business-correct without emitting a search_knowledge tool event; R1 will distinguish this contract issue from true missing business observations. Environment checks use any qualifying observation anywhere in a scenario and unchanged committed state;15/16environment is therefore not15/16correct final answers or per-turn fresh references.

Next: classify earliest actual error and propagated scoring symptoms case by case before any production modification. Full source/prompt/scorer/data hashes and unchanged-before/after validation are in evidence/r0_runtime/experiment_config.json and validation.json. Blind data remains withheld until implementation freeze. No P3/P4.

