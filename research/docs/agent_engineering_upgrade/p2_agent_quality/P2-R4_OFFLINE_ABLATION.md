# P2-R4 fixed-M2 offline source ablation

Candidate/source/Prompt frozen at `44f1031f651637fc96ef5f962f89018b9c1e9748` before any blind execution. All160tasks per arm use the same frozen datasets, Gold/scorers, tool contracts, initial synthetic business state, M2 configuration and scripted provider. Old12corrupt cases are excluded. Distinct source snapshots: C0=0981935; C1=reviewed Context-only74b7047; C2=only Planner/Executor/prompt patch on0981935; C3=combined44f1031. Actual app/eval/data hashes are asserted against the freeze. C2 is an explicitly dirty source-control worktree with exact patch/hash, not an invented commit.

| Group | C0 | C1 Context only | C2 Planner/Fallback only | C3 Combined |
|---|---|---|---|---|
|original80|80/80|80/80|80/80|80/80|
|original7|7/7|7/7|7/7|7/7|
|old16|0/16|1/16|11/16|13/16|
|development|12/30|14/30|22/30|27/30|
|long_window|1/1|1/1|1/1|1/1|
|blind|12/33|12/33|24/33|26/33|

## Per-group decision / state / cost evidence

All metrics below come from unchanged per-turn tool and Goal Oracles. Argument accuracy penalizes missing calls too; it is not solely an executed wrong-ID fraction. Fresh observation additionally requires the right read in its required turn, including changed status on explicit state-event turns. This supplements rather than replaces original success standards. Latency is local end-to-end case time and includes concurrent CPU/fixture scheduling; no causal performance claim. UTF8 input bounds/scripted calls in raw group data are not billed tokens.

| Arm/group | Selection | Arguments | Valid trajectory | Surplus | Tool events | Environment | Fresh reads | Mean/P95 ms |
|---|---|---|---|---|---|---|---|---|
|C0/original80|1.0000|1.0000|1.0000|0|99|1.0000|50/50|270.8/390.5|
|C0/original7|1.0000|1.0000|1.0000|0|14|1.0000|14/14|265.6/269.4|
|C0/old16|0.8387|0.8148|0.0968|25|48|0.9375|21/24|272.8/475.3|
|C0/development|0.9038|0.8125|0.6154|21|51|0.9667|21/28|266.9/449.7|
|C0/long_window|1.0000|1.0000|1.0000|0|2|1.0000|2/2|371.7/371.7|
|C0/blind|0.8519|0.7778|0.4815|22|60|0.9697|28/33|269.5/509.3|
|C1/original80|1.0000|1.0000|1.0000|0|99|1.0000|50/50|272.4/395.7|
|C1/original7|1.0000|1.0000|1.0000|0|14|1.0000|14/14|266.3/273.5|
|C1/old16|0.8871|0.8704|0.1290|24|48|1.0000|23/24|272.2/479.7|
|C1/development|0.9712|0.9531|0.6538|19|51|1.0000|26/28|266.2/431.5|
|C1/long_window|1.0000|1.0000|1.0000|0|2|1.0000|2/2|390.3/390.3|
|C1/blind|0.8704|0.8056|0.4815|23|64|0.9697|30/33|271.4/480.9|
|C2/original80|1.0000|1.0000|1.0000|0|100|1.0000|50/50|275.5/381.4|
|C2/original7|1.0000|1.0000|1.0000|0|15|1.0000|14/14|271.0/283.4|
|C2/old16|0.8387|0.8148|0.8387|0|22|0.9375|21/24|269.9/464.4|
|C2/development|0.8654|0.7812|0.8462|4|30|0.9667|20/28|266.9/442.7|
|C2/long_window|1.0000|1.0000|1.0000|0|2|1.0000|2/2|399.5/399.5|
|C2/blind|0.8426|0.7639|0.8148|3|34|0.9697|27/33|269.0/466.8|
|C3/original80|1.0000|1.0000|1.0000|0|100|1.0000|50/50|274.0/399.2|
|C3/original7|1.0000|1.0000|1.0000|0|15|1.0000|14/14|269.5/279.4|
|C3/old16|0.9032|0.8889|0.9032|0|25|1.0000|24/24|270.6/429.4|
|C3/development|0.9615|0.9375|0.9423|4|36|1.0000|26/28|265.1/429.9|
|C3/long_window|1.0000|1.0000|1.0000|0|2|1.0000|2/2|387.4/387.4|
|C3/blind|0.8796|0.8194|0.8519|3|38|0.9697|31/33|269.3/464.5|

## Attribution and blind discipline

Old16 C0=0, Context-only=1, Planner-only=11, combined=13. Development12→14→22→27 in those arms. Blind33 C0=12, Context-only=12, Planner-only=24, combined=26. Thus most strict-task gain comes from Planner/evidence selection/argument execution, with additional Context contribution and interaction; it is not a new Memory-layer benefit. Per-case transitions are in r4_metrics.json. All original80 and seven historical references remain passing; no original80 task regression. Long-window M2 retains1/1 under all sources.

Blind33was independently authored and first executed after the source freeze. No input/Gold/per-case outcome was viewed during implementation, except blind-safe aggregate static validation. It is now evaluation/regression data, not a future fresh blind set. No candidate change follows blind failures. Source/control results are not four statistically independent samples; they are paired tasks of two module changes.

Observed C3 regressions relative to C0 across all groups: `[{"id": "P2R-B26", "prior": "PASS", "actual": "FAIL", "reasons": ["turn:0:missing_tool", "turn:0:trajectory_invalid", "turn:0:wrong_arguments"]}]`.

## Retained failures and scorer limits

Combined old16 retainsnu12/nu13/nu16 missing registered search_knowledge on legitimate RAG policy paths. Scores are untouched; supplemental business route/evidence judgment is separate, and semantic quality of the scripted fixed answer remains NOT_ASSESSED. Development retainsdv01(order-stage phrasing misclassified by deterministic capability proxy),dv05(negated unnecessary amount/header goal not understood by proxy),dv07(item/quantity paraphrase unsupported by proxy). These cases and earlier candidates remain in new run directories; no Gold or maxcalls changed.

The seven combined blind failures are preserved with exact original reasons in r4_metrics.json. Unknown language, ambiguous references or disagreement between permitted RAG paths and tool-only observation criteria require future development/evaluation, not tuning this same held-out candidate. Zero observed hard safety violations in every group/arm; Owner/Session/HITL/idempotency and transient/freshness integration tests complement task-oracle checks. Real language/semantic judging/token/latency improvements are NOT_RUN until R5 and cannot be inferred from this fixture.

## Post-freeze failure review (no candidate change)

Seven failed blind cases were reexecuted with full local node instrumentation into evidence/post_blind_failures, preserving first scores. post_blind_diagnosis.json links actual routes/tools and categories. B03 misses refund-list capability; B06 misclassifies order-stage phrasing despite correct entity; B26 is the one new regression (only tracking for a financial-total+shipment goal); B28 ignores a negated logistics requirement; B30/B31/B32 take RAG instead of required SKU-specific business tools. No source/input/Gold changes follow these findings. The three Development failures remain, and no universal semantic success is claimed.
