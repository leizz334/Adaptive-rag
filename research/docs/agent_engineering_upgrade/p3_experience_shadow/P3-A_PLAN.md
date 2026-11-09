# P3-A Semantic Calibration and Experience Shadow Implementation Plan

> Execute with superpowers:executing-plans, test-first and task-scoped checkpoints. The user's continuous authorization overrides optional skill approval stops. The task registry/progress/Git are the durable ledger; Initializer is not rerun.

**Goal:** Reassess saved real answers and implement evidence-grounded experience governance without changing Agent decisions.

**Architecture:** An isolated offline pipeline accepts only completed, hash-referenced traces and independent evaluation signals. A bounded deterministic classifier and reflection catalog produce unapproved generic candidates; a separately initialized SQLAlchemy repository stores scoped versioned records. No online service hook or experience recall/injection is added. Default mode is off, active is invalid.

**Stack:** Existing Python/Pydantic/SQLAlchemy async sessions, SQLite development storage and PostgreSQL DDL compatibility checks. No new dependencies, Redis primary storage, vector index or product multi-agent.

**Spec:** User-authorized P3-A0–A6, preserved in the task criteria and this design; prior P2-S remains PARTIAL_PASS.

## Decisions and alternatives

An online post-response hook would require lifecycle/queue/transaction ownership and could leak request data; it is unnecessary for the authorized offline-first scope. An external vector service is unnecessary at this scale. Choose a separate offline runner with a separate SQLAlchemy metadata base and explicit schema initialization: reuse the project's engine/session infrastructure without adding tables to application startup or migrating production. SQLite is executed; PostgreSQL schema compatibility is compiled, live PostgreSQL remains NOT_RUN unless already available.

Raw tools/documents are untrusted observations, never instructions. Only bounded structural signals with immutable evidence refs enter reflection. A small generic lesson catalog can generate auditable candidates without paid reflection calls; it cannot establish learning benefit. MODEL_ASSISTED_REVIEW of saved answers is attributed to independent Codex review, never to a human. Source case IDs remain provenance only, never lesson/applicability rules.

## Global constraints

- Preserve every prior report, Gold, run and task namespace; no paid P2-S reruns.
- EXPERIENCE_MEMORY_MODE is represented by ExperienceSettings.experience_memory_mode: off by default, shadow explicit, active rejected.
- No existing Graph, Context, Memory M2, tools, Retriever, Generate, Judge or business repository behavior changes.
- Store only generic lessons and bounded evidence references in an isolated database; no raw conversation, hidden reasoning, API key or personal order record.
- Scope all operations to verified offline tenant/user/session assertions. No public authentication claim and no cross-session sharing.
- All new APIs/candidates fail closed on malformed, stale, unverified or unsafe evidence. Unknown failures never automatically approve lessons.
- New paid budget120requests/120000tokens/US$2, concurrency1; prefer zero new calls where saved evidence suffices. No new transport is needed unless a real paid experiment becomes necessary.

## Review focus

1. A model claiming a root cause does not prove it: require source refs and distinguish verified failure from likely root.
2. A corrupted/injected/secret-bearing trace must not become a reusable lesson: whitelist structural fields and generic templates, bound input and redact/refuse unsafe text.
3. Expired/deleted/rejected or another user's experience must never match: enforce scope, version and validity at repository and applicability boundaries.
4. Database/parse/reflection failures must not change the completed Agent result: no online wiring; test an isolated observer wrapper and transaction rollback.
5. Offline verification is not human approval or ACTIVE: separate statuses, prohibit active mode, and require independent frozen applicability cases.

## Task sequence

- [ ] **A0** Verify actual remote/source, recompute baseline raw metrics and475tests. Register this phase and freeze history/user files. Commit only A0 evidence/state/plan.
- [ ] **A1** `semantic_review/`: assemble14 actual saved final answers, atomic evidence and supplementary separate-cohort examples. Independent semantic review, second-pass disagreement checks and human packet; label deterministic versus model-assisted, HUMAN_CALIBRATION=NOT_RUN. Validate coverage/refs and commit.
- [ ] **A2** `app/experience/contracts.py`, `taxonomy.py`, `tests/unit/test_experience_taxonomy.py`: write RED tests for verified/likely/unknown/artifact and earliest-node evidence, then minimal bounded classifier. Actual trace diagnoses remain independently sourced. Verify and commit.
- [ ] **A3** `reflection.py`, `shadow.py`, independent ExperienceSettings mode and `tests/unit/test_experience_shadow.py`: RED tests defaultoff/activeinvalid/completed-only/no unsafe lessons/no mutating input/bounded observer errors. Implement no-injection offline queue plus deterministic generic candidates and evidence resolver. Verify and commit.
- [ ] **A4** `storage.py`, `tests/integration/test_experience_storage.py`: RED tests file persistence, same-scope dedup, optimistic versions, lifecycle/review split, delete/expiry, unauthorized reads, rollback and dialect DDL. Separate metadata tables are explicit and reversible. Verify and commit.
- [ ] **A5** `evaluation/`: freeze independently authored applicability/negative controls before evaluation, then compare E0 versus E1 under identical saved-completion replay and canonical answers/tools/business DB. E2 evaluates matching only, no injection. Verify honest metrics and commit.
- [ ] **A6** Full475baseline plus new tests; Ruff/Mypy; old80/16/new30strict controls, Memory/Owner/Session/HITL/idempotency/trace/SSE. Audit all historical and user hashes, produce final report, commit, normalpush and lsremote, STOP.

## Interfaces

A1 supplies semantic annotations and evidence refs, not production Gold or prompt input. A2 supplies typed FailureAssessment with evidence level, chronology, confidence source, hypothesis and references. A3 reflects only qualifying assessments into ExperienceCandidate, initially PROPOSED/unreviewed. A4 persists these scoped candidates with independent review/validation transitions; VERIFIED_OFFLINE never implies approval. A5 consumes candidates and held-out structured task requirements; its Gold is confined to scoring. All experience consumers remain offline.

## Validation and rollback

Use Conda adaptive-rag, workspace scratch basetemp (system temp ACL previously fails). Preserve RED/GREEN output. Every task updates feature-list/progress and commits. Rollback is disabling mode (already defaultoff), removing the independent observer command, and dropping only the isolated experience tables after backup; business schema/production data are never migrated. Histories and failed candidates remain auditable unless explicitly deleted by scoped lifecycle operations.


Ruling A3: historical source compatibility forbids changing existing business Settings. Use a separate offline ExperienceSettings and leave app/config/settings.py unchanged. First fullrun515PASS/1FAIL retained; no old test/Gold/source-freeze is loosened.
