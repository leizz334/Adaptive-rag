# P3-B applicability and human-review handoff plan

> Execute B0 and B1 continuously with test-first verification and task-scoped commits. The user's explicit human gate overrides automatic task progression: push and PAUSE after B1. B2/B3 require actual completed human review and a continuation instruction. Do not reinitialize the project.

**Goal:** Correct scoped principle applicability without weakening execution safety, then deliver seven saved real answers for human calibration.

**Architecture:** Retain the original C0 matcher, catalog, candidate records, business Agent and all old Gold. Introduce a versioned offline-review applicability contract that separates principle relevance from execution/injection authorization. Every positive advisory match remains non-executable, with fixed scope/version/expiry/provenance gates and context-specific safety obligations. Empty business evidence is explicit, distinct from absent/untrusted feature provenance. No retrieval or injection is built before B2 authorization.

**Stack:** Existing Python/Pydantic/EvidenceResolver/pytest; deterministic evaluation and CSV/Markdown generation. No dependencies or new model requests needed in B0/B1.

## B0: diagnosis, minimal repair and independent evidence

- [x] Verify local/remote P3-A04ccadb, fresh548tests, raw12TP/0FP/8FN/76TN and3NEEDS_REVIEW records; preserve all historical/user files.
- [x] Trace each of8misses to required/evidence/exclusion checks. Record missing evidence versus known-empty, principle relevance versus act authorization, and all alternative explanations.
- [x] Write RED unit tests for conditional relevance with non-execution obligations, unsafe scope/stale/expired/rejected/counterfeit or malformed source rejection and default compatibility.
- [x] Implement new `app/experience/review_applicability.py`; keep existing matches_offline unchanged. The new API has no tool/prompt/retrieval surface and never authorizes execution or injection.
- [x] Freeze24new development cases and separately authored32blind cases/Gold. Holdout author sees public principles/spec only, not candidate implementation, development labels or outcomes. Record procedural isolation limits.
- [x] Independently review code, fix important findings with RED/GREEN, then freeze source/scorer before first blind use.
- [x] Run common C0/C1 on unchanged consumed32diagnostic cases, development and new blind. Score relevance and safety obligations separately. Retain FP/FN and per-family strict all-case results. Applicability evidence does not approve experience content, storage status or production activation.
- [x] Run appropriate full/regression checks, update B0 state and commit. No Gold relaxation, case-ID logic or post-holdout tuning.

## B1: human review package

- [ ] Reuse only seven actual R1public final answers from existing immutable captures, with original queries and actual tool/RAG observations.
- [ ] Generate Chinese index, packet and BOM CSV with blank human cells; priority PSV04/PSV13/PSV16. AI labels/controversies are separately disclosed and not copied into human verdicts.
- [ ] Verify exact text and source hashes, seven rows, blank PASS/FAIL/UNCERTAIN choices, frozen query/answer identities and absolute plus repo-relative paths.
- [ ] Record full current validation and preservation/secret audit, commit/push and verify ls-remote. Mark WAITING_HUMAN_REVIEW and STOP.

## Deferred B2/B3 gate

Import, trust validation, qualified experience retrieval/injection, benefit/negative-transfer studies and optional paid tests belong to B2 after the user's review and continuation. B3phase regression and P4_E2E_TEST_PLAN.md follow B2. They are registered but NOT_RUN now. Never auto-fill review, treat a blank CSV as approval, activate experience memory or start P4.

## Design choices and limits

Removing exclusion tags would erase the distinction between a safe principle and unsafe permission. Instead C1 returns a versioned review decision, a source-candidate fingerprint and mandatory obligations, always NO_EXECUTION/NO_INJECTION. Scope, owner, HITL, idempotency, freshness and untrusted-content boundaries remain intact. This measures structured applicability, not language understanding or task benefit. Human approval is a separate missing gate.

Evidence data/Gold and implementation hashes are immutable after freeze; source-only fixes precede blind evaluation. User authorization already covers execution of B0/B1, so no extra design approval is requested. Rollback is removing the new review API/runner; original matcher/business source is preserved.
