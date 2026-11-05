# P2-R3 decision design and rollback boundaries

Changes follow R1's actual node evidence, not blind results. No new Memory tier, Experience Memory, Graph loop or product Multi-Agent. The compiled Graph remains one plan→execute→generate path per business turn; no autonomous replanning loop is needed for these failures. Production changes stay in existing ContextBuilder, ChatService context binding, Planner/Executor and Planner prompt.

## Context and entity provenance

SelectedContext adds `order_ids`, `original_query`, `owner_user_id`, `session_id`. Scope is stamped only after SessionRepository validates the session owner. This is reference provenance, never authenticated production identity or permission. Owner/session values stay out of model context; existing M3 public activation remains disabled. Current explicit IDs override historical targets. Explicit coordinated read goals can carry multiple IDs, while singular reference after an equally salient pair clarifies. Multiple ambiguous writes/corrections stay conservative.

Reference grammar recognizes demonstrative noun/classifier forms and specific business ellipsis without full-utterance templates. General policy/social content remains outside order binding. Only user messages and existing validated summaries contribute targets; assistant/tool text cannot grant authority. Explicit first-mention reference can use intact recent chronological user history, but must clarify when older summaries or discarded window messages make first-in-session provenance unknown. Summaries retain recent entities, not an ordinal history. Business state always comes from fresh permission-checked tools.

The legacy effective-query marker remains for compatibility with existing Intent/Router/scored fixtures. Planner receives raw user goal separately from that grounding text, so the marker's instruction to query fresh status does not become a new shipment/header task requirement. Existing selective per-node context views remain bounded; no full-history injection into every node.

## Planner and execution

`create_plan(query,intent,summary,*,raw_query=None,order_ids=())` keeps the previous positional API. Real model planning stays primary. Actual tool JSON Schemas join the existing catalog, and the prompt distinguishes task evidence from bound entity and authorization. Offline fallback uses a small header/shipment/items capability ontology rather than unconditional skill-tool expansion or whole-Chinese-query status templates. That deterministic proxy still has known lexical/negation limitations; it is not a claim of model semantic understanding.

Real catalog defaults preserve unknown/mixed skill capabilities. A lexical header cue cannot prove an unfamiliar additional goal is absent; only a tiny fully accounted header-only request may narrow. Transportation-history and package-transfer obligations remain available even when they contain status/payment wording. The prompt asks for necessary evidence and termination, but no side effect is authorized by the model's assertion of completion.

Before execution, known tool arguments are structurally validated and order targets must be grounded. Missing, placeholder or foreign/unmentioned model IDs do not reach tools; missing targets produce an empty clarification plan and the existing `missing_order_id` response path. Explicit multi-order reads can be expanded to their named targets. Confirmed writes still use the original server-stored proposal, Owner/business checks and existing idempotency; no model replanning of approved write parameters.

Read deduplication happens after actual outcomes, within one Executor invocation. Only successful observed capabilities and deterministic rejections block exact repeated reads. Transient failed reads can use bounded planned attempts under existing tool/step limits. Successful fallback results are cached by actual fallback tool+arguments for that turn; reusing a header result does not claim shipment evidence. Cache hits do not emit fake Tool.run events. Every nonread attempt (including a denied write) clears observation reuse; nothing survives a new turn. Exact repository not-found rejection suppresses other read capabilities solely for the same protected entity in that turn, without blocking another target or a later fresh query. Generic argument errors do not assert an Owner denial.

## Validation and retained candidates

- Context initial RED7/2PASS →32context/regressionGREEN; independent review RED2 →27GREEN for ordinal provenance and conjunctive reads.
- Planner/Executor initial RED14/4PASS →34targetedGREEN; first independent review RED5/1PASS →41GREEN. Review then found a repeated successful fallback dispatch: RED1 →43GREEN; malformed nonstring target guard also reproduced before repair.
- Independent review's original five findings regraded with14focused checks; final fallback reuse regraded with9freshness/target/write/refusal controls. No remaining material finding in that review scope.
- First combined development candidate: original80=80/80, old16=13/16, Development27/30, long-window1/1, zero observed hard violations. These are OFFLINE_SCRIPTED results before final fallback-cache repair, preserved as `20261105_C3_dev_candidate`. The three old remaining failures are the frozen policy tool-event contract disagreement; no Gold changed. Development failures expose fallback language/negation coverage and remain recorded rather than being silently removed. No blind run has occurred at design freeze.

Context-only rollback checkpoints are `7cd61be` and independently reviewed `74b7047`. Planner/Executor/prompt changes have an independent patch and later task checkpoint. C0 uses0981935; C1 uses reviewed Context-only; C2 applies only Planner/Executor/prompt changes to0981935; C3 combines. App/eval/Prompt/data hashes identify every arm. Fixed M2, tools, Gold, state, scorer and output budgets isolate effects; actual Prompt changes belong to Planner, not Memory. Any later reviewer correction receives a new output/source freeze, never overwritten evidence.

Final candidate freeze requires full tests, Ruff/Mypy and source review before revealing the independently authored33-case holdout. No blind failure will be used to tune that same frozen candidate. Real R0/R1 comparisons use their inherent prompt differences explicitly and common sampling/budget settings.
