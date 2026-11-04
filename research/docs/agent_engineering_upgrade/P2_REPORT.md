# P2 — Memory V2 + Context Engineering

Date: 2026-11-04 (Asia/Taipei). Branch: `codex/p2-memory-context`. Worktree: `D:/Code/Adaptive-rag/.worktrees/p2-memory-context`.

**Status: PARTIAL_PASS.** Authorized local implementation/checkpoints and offline evaluation are complete. Original P1 remains PARTIAL_PASS; real baseline remains PARTIAL (9valid/15selected). No additional paid model request, P3 or P4 was started. No real-model Memory/JSON improvement is claimed.

## Delivered and verified

| Task | Delivery | Verification / limits |
|---|---|---|
| P2-A | Preserved real evidence;7references/4truncations/3argument failures/case call cost classified;6-case pre-P2 supplement plan; separate JSON repair |212original baseline tests;20targeted reliability/judge/tracing tests; supplement NOT_RUN pending explicit cost authorization |
| P2-B | Selective owner-scoped Context Builder; user-origin entity hints; raw request unchanged; current tools/permissions/confirmations retained | Original7 passes7/7 OFFLINE;229full tests at checkpoint; narrow heuristic has held-out limitations |
| P2-C | Versioned owner/session/provenance/watermark/expiry summary, incremental batches, original history preserved; full payload/output budget preflight |236full tests, mypy135files; no summarization LLM call; long-window fresh observation restored but strict Planner trajectory still fails |
| P2-D | Consent/version/source/update/invalidation/expiry/delete preference prototype; task-local verified request scope | Lifecycle/tenant/user/public-off/context-reset tests; real public cross-session memory NOT_ENABLED |
| P2-E | Paired rule/scripted M0–M3, independently frozen held-out12, separate initial/reviewed outputs and preserved failures | Final247tests;heldout3/12;paid model arms NOT_RUN; overall empirical acceptance remains partial |

Architecture/design: [P2_DESIGN.md](P2_DESIGN.md). Source guidance: [Context](P2_CONTEXT_GUIDE.md), [Summary/budget](P2_SUMMARY_GUIDE.md), [M3](P2_LONG_TERM_MEMORY.md). Changed implementation: `app/memory/{context,summary_state,long_term,budget,summarizer}.py`, service/state/graph/node wiring, SessionRepository, provider finish-reason/budget handling, judge allowance/settings; `.env.example` documents switches. Existing P1 fixture explicitly defaults M0; Gold/scorers/old evidence stay unchanged. No new dependencies or migrations.

## Real baseline and reliability gate

The retained DeepSeek run used80HTTP/58342tokens, task2/9 and reference0/7; those are historical measurements, not P2 costs. Its four malformed256-token outputs follow Generate in the AGENT sequence, attributable by source-chain inference to FaithfulnessChecker; raw checker prompts/answers were not archived so exact checker hash attribution is unavailable. See [P2-A diagnosis](P2_A_BASELINE_GATE.md) and p2_evidence/P2-A-analysis.json.

Independent repair: non-retryable structured finish_reason=length rejection, actual model/finish metadata preservation, INVALID_OUTPUT separated from API/JUDGE_ERROR, configurable judge allowance512(default; bounded256..2048), no retry. Mock regressions passed. **Real post-repair truncation rate is NOT_RUN**;512does not guarantee no truncation. Intent/Router caps and Planner policy were not increased/changed. This repair is held constant in all Memory arms; its real quality/cost benefit is not mixed into Memory claims.

Six pre-P2 cases (greeting, argument_binding, cancel_pending, foreign_order, cross_user_session, injection) remain awaiting explicit additional-fee authorization. Plan uses a NEW reserved Run ID, source `3c373ca502e2e08b4a343d751500c7ce77b28415`, isolated data, serial execution, no retries; estimate12–25calls plus probe/10000–20000tokens, hard40requests/30000tokens. Currency cost UNKNOWN until pricing/account is checked at an authorized execution. No such requests were made.

## Memory-only offline comparison

Both OFFLINE_RULE and prompt-consuming OFFLINE_SCRIPTED produce the same correctness outcomes under unchanged scorers:

| Metric | M0 | M1 | M2 | M3 synthetic verified scope |
|---|---:|---:|---:|---:|
| Original80 Task Success |66/80 (82.5%)|73/80 (91.25%)|73/80 (91.25%)|73/80 (91.25%)|
| Original7 reference success |0/7|7/7|7/7|7/7|
| Original80 selection / arguments |95.76% /92.93%|100% /100%|100% /100%|100% /100%|
| Original80 environment + observations |77/80|80/80|80/80|80/80|
| Held-out12 Task Success |2/12|3/12|3/12|3/12|
| Development long-window task |0/1|0/1|0/1|0/1|
| Development long-window fresh observation/state |0/1|0/1|1/1|1/1|

The independently authored held-out set was frozen before Memory development, SHA256 `f1200034a4048b20768ba2097bc408097f760dd7974ae8fe2ed093a15343fefc`; it was first viewed/evaluated in E. **Nine held-out failures remain**: unsupported reference expressions/missing required tools/incorrect or missing arguments, and three missing changed-state observations. No dataset or trajectory relaxation followed these failures. Original80's remaining7ownership-fallback redundant-call failures are retained. Long-window M2 retrieves the correct fresh entity/state but unchanged Planner's extra track_shipment exceeds the strict case trajectory, so Task remains FAIL. See [P2_ABLATION.md](P2_ABLATION.md) and p2_evidence/P2-failed_cases.md.

These fixtures test engineering behavior, not DeepSeek semantics, independent judging or general production performance. All real M0/M1/M2/M3 reference/task/tool/state/token/latency comparisons are **NOT_RUN**. The held-out result prevents a general reference-resolution success claim.

## Safety, cost and latency

Final full247tests passed with one existing LangChain deprecation warning; all original safety/HITL/owner/session/idempotency/tracing regressions still pass. Eight93-case arms in each offline snapshot show zero observed hard forbidden/ownership/unconfirmed-write violations. This is synthetic regression evidence, not real authentication, concurrency or security certification. Public API user_id still is not a verified login; M3 production store/scope are deliberately not wired.

New paid API calls=0; new billed tokens=0. Actual real-model token usage is NOT_RUN. Scripted original80 uses521local fixture responses in each arm, with conservative input bounds M0=1185055, M1/M2=1253027, M3=1260587UTF-8-based units. These are not billed tokens. No summary call was added; M2 long-window correctly invokes additional live processing compared to M1clarification, so lower cost is not claimed.

Recorded scripted original80 mean/P95 offline case latency(ms): M0=242.349/427.301, M1=234.239/288.849, M2=241.794/457.691, M3=244.180/465.676 (nearest rank). Includes fixture initialization/local CPU contention and concurrent verification; cannot establish remote latency or Memory overhead. Per-group values in p2_evidence/P2-E-metrics.json are authoritative. Runtime ChatResponse usage is not a whole-workflow billing meter; future paid comparisons must meter every request, including errors/truncations.

## Review, reproducibility and remaining gates

Fresh whole-branch review found two regressions: temporal generic policy/how-to text incorrectly required an order, and M1 ignored history windows above20. Independent RED tests reproduced both; code/test fix at `40d86224e7f3f12b952a86a8aa6e1301c87199f2`, targeted19tests passed and focused independent regrade14passed with no remaining findings in that scope. These repros were independent of held-out samples. First8-arm results were committed unchanged at `81c174fee42f89e78e8781eb1d416bb6acef39e0`; final replay uses40d8622and a NEW output. All normalized scenario outcomes agree across the two snapshots; failures remain visible.

Verification recomputes3280saved turn scores from unchanged Gold, confirms66prior artifact hashes, held-out/ablation/scorer hashes, both8-arm results and247test evidence, old feature state and paid0 labels. Mypy137source files and Ruff check/format passed. Commands (Conda adaptive-rag, no paid calls):

```powershell
conda run --no-capture-output -n adaptive-rag python -B research/docs/agent_engineering_upgrade/p2_evidence/verify_p2.py
conda run --no-capture-output -n adaptive-rag python -B -m eval.memory_ablation --output <NEW_OUTPUT_PATH.json>
```

Original P1/real evidence is immutable; source3c373ca remains available for the pre-P2 supplement. Complete original DB state is checked by the unchanged runtime goal oracle; saved evidence includes tool events/state maps, not a full production data snapshot. Summary compression is deterministic/extractive; broad semantic constraints/LLM summary fidelity, real tokenizer/window limits, production multi-instance concurrency/load and verified authentication remain unproven. M3 is ephemeral, preference-only, with no claim of live cross-session benefit. Preserve held-out and Planner residuals as follow-up quality work rather than silently tuning/relabeling them.

Phase is PARTIAL_PASS: A–D local mechanisms are verified; E's generalization/real-quality gate remains partial. No supplement or new fees were authorized. Exact task/checkpoint hashes and actual normal push result are recorded in feature-list.json, progress.txt and p2_evidence/P2-git-delivery.json. Unrelated root changes are preserved. **After final delivery STOP for review; do not start P3/P4 or new paid runs.**
