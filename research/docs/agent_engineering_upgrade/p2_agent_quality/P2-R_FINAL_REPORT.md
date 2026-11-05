# P2-R final report

Phase quality: **PARTIAL_PASS**. The candidate improves strict tool/state task success on development, an independently withheld Chinese holdout, and a small real DeepSeek paired subset. One new offline holdout regression, incomplete real coverage, structured-output truncation, and deficient fallback answers remain. These results do not establish universal reference resolution or complete final-answer semantic accuracy.

Production source was frozen at `44f1031f651637fc96ef5f962f89018b9c1e9748` before holdout execution. Source baseline is the user-pushed P2-Q commit `09819352cc6df98b9f8cb42ffb56e9c8365b5793`. No production changes followed holdout results. Delivery/checkpoint commits are separate metadata, experiments, and validation changes; see `evidence/delivery.json` for verified remote commit and Git log for the final reporting checkpoint.

## Diagnosis and implementation

Full baseline-source node reexecution reproduced old16 exactly: 0/16 strict tasks, 15/16 environment, 25 surplus calls (21 shipment and four order reads). First primary causes: 13 extra-tool plans, one entity-binding failure, one ambiguous-reference/empty-argument failure, one scorer-contract dispute. Several consequences can coexist; primary counts are not duplicated. The environment oracle often permits any qualifying observation across turns and unchanged DB state, which explains its higher score. There was no recursive planning loop: unconditional expansion of a skill's tools created most surplus calls. The old12 ASCII `?` fixture is retained only as forensic evidence.

Five application files changed: Context preserves raw goal separately from scoped entity provenance; ChatService stamps context scope after session-owner validation; Planner uses actual tool schemas and grounded parameters; Executor reuses only successful same-turn read evidence and deterministic same-target refusals; Planner Prompt separates goal, evidence, and termination. Transient read failures remain eligible for bounded planned attempts. Writes invalidate read reuse and retain existing permission, fresh-state, confirmation and idempotency checks. Current explicit targets supersede history; uncertain first-ordinal references after cropping clarify. No additional Memory layer, Experience Memory, product Multi-Agent, auth bypass, Gold/scorer change or Graph rewrite was added.

RED/GREEN repros and independent pre-freeze review are in R3 evidence. Rejected intermediate candidates and review findings remain recorded. Rollback boundaries: C0 baseline; C1 `74b7047` Context-only; C2 exact recorded Planner/Executor/Prompt patch on baseline; C3 frozen combination. C2's intentional uncommitted patch is identified by exact app hashes rather than a fictitious commit.

## Offline controlled results

All arms use M2 and the same synthetic business fixtures, datasets, Gold, tool definitions, scorer and seed clock. Different source implementations are actually imported from separate worktrees. Each frozen run contains 160 tasks. The original seven references are a subset of80, not extra independent samples.

| Dataset | C0 baseline | C1 Context | C2 decision/execution | C3 combined |
|---|---:|---:|---:|---:|
| Original80 |80/80|80/80|80/80|80/80|
| Original7 references |7/7|7/7|7/7|7/7|
| Old16 |0/16|1/16|11/16|13/16|
| Development30 |12/30|14/30|22/30|27/30|
| Blind33 |12/33|12/33|24/33|26/33|
| Long window |1/1|1/1|1/1|1/1|

Most gain belongs to evidence selection/decision execution, with additional Context contribution and interaction. It is not a new Memory-layer gain. Blind outcomes: 15 improvements, one regression, net14. Original80 regressions: zero. Blind regression B26 incorrectly drops the financial-total evidence requirement from a mixed shipment/total task; this is retained, not tuned away. All arms observed zero hard safety violations.

C3 old16: selection90.32%, arguments88.89%, valid trajectory90.32%, surplus0, environment16/16. C3 development: selection96.15%, arguments93.75%, trajectory94.23%, surplus4, environment30/30. C3 blind: selection87.96%, arguments81.94%, trajectory85.19%, surplus3, environment32/33. These are turn-averaged scorer metrics, not all-task binary rates. Full per-source/group metrics and latencies are in `evidence/r4_metrics.json`. Offline latency was measured under fixture/CPU contention; no causal speedup is claimed.

The independently authored blind set was withheld from implementation until the recorded source freeze. Isolation is procedural, not cryptographic. Development30 and blind33 exceed the requested minimum24 each and cover distinct business/state/interaction goals, not only ID substitutions. UTF-8, entity/state consistency, legal paths and overlap gates passed with SHA256 manifests. The evaluated blind set is now regression data, not a future fresh blind set. Standard fixtures cannot inject every tool failure; independent integration tests cover transient errors and untrusted/assistant-only content.

## Real DeepSeek pairs

New run `20261105_R5_pairs_01`, official endpoint `https://api.deepseek.com`, returned model `deepseek-flash`. Same M2, endpoint/model, fixtures, Gold, scorer, temperature0 and output schedule; intentional source Prompt/catalog differences are hashed and disclosed. This compares complete Agent implementations, not isolated model weights or real Context-only/Planner-only causal effects.

| Completed-pair scope | R0 | R1 |
|---|---:|---:|
| Development |3/5|5/5|
| Blind subset |1/3|2/3|
| All |4/8|7/8|

R1 overall selection91.67%, arguments90.91%, trajectory91.67%, environment8/8, necessary fresh business reads11/12; R0:75%,63.64%,66.67%,7/8,7/12. Surplus calls1→0, but total actual tool events10→12 because necessary evidence is added. Prompt/completion tokens increase from39,632 to49,169 on completed paired arms. There is no overall API cost or average-latency reduction claim. R0 B10 failed at a pre-model clarification gate and had zero HTTP calls; its actual Agent failure is included, never described as a DeepSeek response.

109 HTTP attempts:108 durable HTTP200 responses and one uncertain ConnectError at B05/R0 Intent. Reported tokens88,858; conservative unknown reservation3,981; accounted92,839. Hard limits420HTTP/420,000tokens/estimatedUS$3, per-group24, concurrency1; no automatic retries. Peak-rate estimate US$0.0472881 includes reservation and is not a settled invoice. Price source: [official DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), checked2026-11-05, input$0.30/M and output$1.20/M without cache discounts. Observed alias does not independently identify backend weights.

The uncertain request is durably PENDING and **must not be resent**. Planned B05/B30/B25 pairs and optional repetition remain incomplete/NOT_RUN. Eight of11 planned pairs completed; repeat-based nondeterminism check NOT_RUN. The stop is infrastructure failure, not model-task failure. No more paid calls were made for final verification. Historical P2-Q's pending request194 remains untouched.

Measured all-attempt latency230.909s, including failed-connect latency5.097s. R0 task mean/P95=14.865/24.180s; R1=15.170/23.506s. R0 HTTP mean/P95=2.167/3.835s; R1=2.011/3.401s. Model service/sampling can vary despite temperature0; three completed blind pairs cannot establish population generalization.

Seven JSON truncations remain (six Judge, one baseline Planner; cap512). No extra schema failure; one missing transport response is infrastructure, not an eighth model JSON error. The raw helper's eight-error diagnostic is retained with explicit corrected classification. Counts include failed-output recovery calls and the probe; completed-response local replay is not billed again.

Exact network-blocked local replay captured actual final-answer stages using only completed durable responses. All16 groups matched request hashes, consumed responses and reproduced original scores; zero new paid calls/tokens. First local replay failed due integer0 versus float0.0 wire encoding; both rejected replay and corrected helper regression evidence are preserved, with no journal or source edits. Replayed node traces are explicitly reconstructed local execution, not fabricated historical traces.

## Remaining failures and semantic limits

- Old16: nu12/nu13/nu16 retain strict failures because legitimate RAG policy paths omit the Gold-required registered search_knowledge event. Original score is preserved; supplemental business-route judgment does not certify final-answer semantics.
- Development: dv01 order-stage wording, dv05 negation, dv07 item/count paraphrase remain unsupported by deterministic capability selection.
- Blind: B03 refund capability, B06 order-stage wording, B26 mixed financial+shipment regression, B28 negation, B30 inventory, B31 warranty, B32 product detail. SKU tasks can route to RAG without required live business tools. Seven failures remain; no post-blind tuning.
- Real B31 fails both variants; after Judge truncation, unchanged faithfulness fallback produces the false message “当前未配置生成模型” and an unrelated warranty excerpt. Real dv06 strict PASS can also lose goal coverage in its final fallback answer. Therefore real7/8 is the **frozen tool/state task oracle**, not complete end-to-end semantic answer success. `evidence/r5_semantic_limitations.json` retains exact evidence. Semantic success rate is NOT_ASSESSED.
- Structured-output caps/fallback robustness and conservative lexical/intent capability coverage need separately frozen future candidates and new independent evaluation. This phase stops without a post-holdout patch.

## Final regression and preservation

Fresh full pytest including all application tests, old P2-Q real-helper mocks, new instrumentation, bounded-real harness mocks, and replay-wire tests: **344 passed**, one dependency deprecation warning. Ruff check and format plus Mypy are recorded in `evidence/r6_checks.json`. Initial final-lint attempt identified one import-layout issue and three unformatted experiment helpers; fixed only experiment/report code. Earlier five helper scripts were also formatted; two unused imports removed with AST proof. No app or frozen paid harness changes occurred.

P1's original M0 evaluation remains13/14 (context_loss failure), environment14/14, matching its known no-history limitation. Full160 C3 OFFLINE_RULE compatibility independently matches scripted C3 outcomes. Original80/seven/long-window and all safety tests continue passing. Security suite covers Owner, Session, HITL, idempotency, live-state changes, JSON errors, bounded retry, tracing-off and local tracing; zero observed hard violations is not a comprehensive security proof.

Preservation validation verifies174 original evidence files,20 user files including .env, old task registry unchanged outside the new namespace, and progress prefix preserved. Gold/scorer/eval files are unchanged. All four frozen app snapshots and both datasets retain their hashes. Phase files were scanned locally against the actual API key without emitting it; no credential is committed. Runtime lock stays local/ignored; its earlier index inclusion is removed without deleting the local file. Temporary test directories are retained safely and excluded from commits.

## Checkpoints, delivery and recovery

R0 b132be8; R1 68951ad; R2 93fee3a; R3 Context checkpoints7cd61be/74b7047 and final44f1031; R4 aef3101; R5 03bd21f. R6 has its own verification checkpoint followed by a delivery-state checkpoint. Actual full hashes live in feature-list.json, progress.txt, Git log and delivery.json. `passes` represents verified task evidence/engineering acceptance; phase quality remains PARTIAL_PASS and real coverage remains PARTIAL.

Authorized destination: origin `https://github.com/leizz334/Adaptive-rag.git`, branch `codex/p2-agent-quality`, normal push only. Remote verification and exact HEAD are persisted separately after actual delivery. If transport fails: retain all local commits and run `git push origin codex/p2-agent-quality`, then `git ls-remote origin refs/heads/codex/p2-agent-quality`. Never rerun paid requests to recover Git delivery. Original user workspace remains preserved; branch location is recorded in delivery evidence.

**STOP. P3_STARTED=NO; P4_STARTED=NO.**
