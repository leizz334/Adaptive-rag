# P2 Memory V2 implementation plan

> Execute inline with superpowers:executing-plans, test-driven-development, verification-before-completion and final requesting-code-review. User explicitly authorized continuous execution of all five tasks; no extra paid calls.

Goal: implement selective session context, incremental summaries and a safely gated long-term prototype, with honest offline ablations.
Architecture: P2_DESIGN.md is the binding design. Existing service/graph/repositories, no new dependencies or production data.

## Global constraints

- Retain P1 PARTIAL_PASS and real baseline PARTIAL; immutable old Gold/evidence/results. No Initializer rerun, P3/P4, secret commits or paid API requests.
- Each atomic task gets RED/GREEN where behavior changes, acceptance validation, persistent status and an independent local commit. Automatically continue.
- Only authorized phase files; preserve unrelated root working changes. Final normal push only to authorized leizz334/Adaptive-rag P2 branch.

## Review focus

- Ambiguous/incorrect/assistant-origin/cross-user entities must not trigger wrong tool parameters.
- Stale summaries/business state must not replace live reads, permissions or confirmations.
- Complete prompt budget, invalid/expired/conflicting summary and long sessions must remain bounded and recoverable.
- Public user_id/configuration must never activate cross-session M3; update/delete/expiry and tenant isolation must be tested.
- Paid-not-run, model truncations, rule fallback and offline ablation improvements need distinct evidence and denominators.

## P2-A baseline gate (two independent checkpoints)

- [x] Read audits and raw frozen real run, reproduce node request hashes where possible, categorize seven references/four truncations/parameter errors and per-case calls/tokens.
- [x] Freeze immutable prior artifact inventory and held-out dataset hash; create six-case supplement plan with pre-P2 commit, new Run ID, serial budgets and token estimate. No execution.
- [x] Add targeted failing truncation/classifier-output tests, implement minimal finish-reason validation and separate output budget control, verify fallback/HTTP regressions. Report repair separately from Memory.

Files: P2_A_BASELINE_GATE.md, P2_JSON_RELIABILITY.md, p2_evidence/, app/providers/base.py, deepseek.py, app/agents/nodes/intent.py, app/retrieval/adaptive.py, app/config/settings.py and targeted tests.

## P2-B Context Builder + M1

- [x] RED: selective relevant history/entity resolution; current explicit target wins; assistant/order ambiguity/current foreign user safety; original seven cases with unchanged scoring.
- [x] Implement Context Builder and scoped state views, wire owner-validated history to Intent/Router/Planner/Generate without changing raw request/authorization input. Add explicit M0 fixture compatibility.
- [x] GREEN: context unit/integration/SSE/owner/HITL tests; record Memory-only original seven results and token estimates, checkpoint.

## P2-C Summary + M2

- [x] RED: persistent restore beyond recent window, incremental watermark, key entities, conflicts/expiry/invalid summaries, full request budget and long-session behavior.
- [x] Extend existing repository/summary/budget modules, pre-inference restore/compaction and safe persistence; reuse existing summary field and preserve raw messages. No extra model call.
- [x] GREEN: long conversation, summary recovery, payload limits and original regressions; checkpoint.

## P2-D isolated M3 prototype

- [x] RED: verified tenant/subject + consent gate, provenance/version/update, expiry/invalidation/deletion and cross-session isolation; client spoofing/config cannot enable production recall.
- [x] Implement minimal in-memory stable-preference store with server-only injection and explicit public default-off behavior.
- [x] GREEN: isolated lifecycle tests; record M3 production NOT_ENABLED, checkpoint.

## P2-E ablation and final regression

- [x] Run frozen original seven + P1 fixtures + held-out + long-window scenarios under paired offline M0/M1/M2 and authorized synthetic M3; unchanged Gold/success scoring. Keep JSON-only arm distinct.
- [x] Report task/reference/tool argument/selection/state/safety/input-estimate/latency and model-call accounting; real arms all NOT_RUN and billed P2 tokens=0.
- [x] Full existing + new regressions, lint/format/type checks, immutable evidence and held-out hash checks, fresh branch review and required fixes.
- [ ] P2_REPORT.md, P2_ABLATION.md, p2_evidence/results.json, failure/limits/paid supplement plan/state/true commits and actual normal push outcome. STOP before P3/P4.
