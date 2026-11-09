# P3-B0 Experience applicability

B0 engineering and bounded relevance validation completed. Human approval and injection benefit remain unverified. All three original candidate records stay NEEDS_REVIEW / UNREVIEWED; none is promoted to VERIFIED_OFFLINE by this task.

## Verified baseline and minimal change

Local/remote P3-A baseline 04ccadb661bacfe4b09616ad11226288d4af8bf3 was verified before creating the isolated codex/p3-experience-validation worktree. Fresh baseline548tests passed. Pre-evaluation source/data checkpoint is a92164d. The original app/experience/applicability.py, catalog, candidate records and all business/Graph/M2/authorization code remain byte-identical.

The original boolean conflates principle relevance with permission to use an experience. Its exclusions are appropriate as execution restrictions, but suppress useful review of how to handle risk. New review_applicability.py is a separate versioned advisory API. It returns MATCH_FOR_REVIEW, NO_MATCH or DEFER; every outcome forbids execution/injection/human approval and retains the original execution exclusions. It does not wire a new matcher into the Agent or implement B2 retrieval/injection.

Identity/scope/version/expiry/rejection checks precede private reference resolution. Claimed tags must match hash-bound reviewed structural observations; provenance failure is DEFER. Known-empty evidence differs from unknown evidence. Risky relevant contexts carry explicit pending-write, untrusted-data, clarification, freshness, evidence-limit and Judge-category obligations. No permission, Owner, HITL or idempotency check is relaxed. A MATCH_FOR_REVIEW must never be interpreted as injection eligibility.

## Eight frozen misses

These are candidate/task judgments, not eight distinct user tasks. The original32case Gold and baseline TP12/FP0/FN8/TN76 are reproduced exactly. Root cause is demonstrated by the old matcher path and catalog exclusions, not inferred from final failure alone.

| Frozen case | Candidate family | First excluding v1 condition | C1 disposition |
| --- | --- | --- | --- |
| e2-copper-brook | fallback_evidence | write_unconfirmed | Review only; original restrictions retained |
| e2-pearl-ladder | fallback_evidence | write_unconfirmed | Review only; original restrictions retained |
| e2-pearl-ladder | judge_output | write_unconfirmed | Review only; original restrictions retained |
| e2-aqua-violin | mixed_evidence | untrusted_input | Review only; original restrictions retained |
| e2-umber-ribbon | fallback_evidence | untrusted_input | Review only; original restrictions retained |
| e2-turquoise-leaf | mixed_evidence | clarification_required | Review only; original restrictions retained |
| e2-tangerine-wheel | fallback_evidence | required evidence_available absent | Review only; original restrictions retained |
| e2-cerulean-net | judge_output | untrusted_input, write_unconfirmed | Review only; original restrictions retained |

Mixed2misses are untrusted text and ambiguity; Judge2misses are pending-write/untrusted contexts; Fallback4misses include pending writes, untrusted data and unavailable evidence. C1 attaches constraints instead of declaring a safe operation possible. Unknown evidence permits only limitation-oriented review, never invented facts.

## Controlled comparison

C0 is the unchanged v1 matcher; C1 is source-bound principle review. Same three candidates, task inputs, Gold, scope, fixed UTC clock and source versions. Predictions are computed before loading each cohort Gold. Original relevance labels are unchanged. Permission semantics are deliberately separated in C1; these results measure relevance, not equal production authorization policies.

| Cohort | Arm | TP | FP | FN | TN | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| consumed_diagnostics (32 tasks ×3candidates) | C0 | 12 | 0 | 8 | 76 | 100.00% | 60.00% |
| consumed_diagnostics (32 tasks ×3candidates) | C1 | 20 | 0 | 0 | 76 | 100.00% | 100.00% |
| development (24 tasks ×3candidates) | C0 | 6 | 3 | 6 | 57 | 66.67% | 50.00% |
| development (24 tasks ×3candidates) | C1 | 12 | 0 | 0 | 60 | 100.00% | 100.00% |
| blind_holdout (32 tasks ×3candidates) | C0 | 10 | 0 | 9 | 77 | 100.00% | 52.63% |
| blind_holdout (32 tasks ×3candidates) | C1 | 19 | 0 | 0 | 77 | 100.00% | 100.00% |

| Candidate | Old cohort C0→C1 TP/FN | New blind C0→C1 TP/FN | C1 blind contract | Approval |
| --- | --- | --- | --- | --- |
| mixed_evidence | 7/2→9/0 | 6/3→9/0 | PASS bounded relevance/guards | Pending human/B2 |
| judge_output | 2/2→4/0 | 2/2→4/0 | PASS bounded relevance/guards | Pending human/B2 |
| fallback_evidence | 3/4→7/0 | 2/4→6/0 | PASS bounded relevance/guards | Pending human/B2 |

C1 safety conflicts and missing-required-guard decisions are0in all cohorts. C0 has no structured guard envelope, so this does not claim guard equivalence. Three development C0positive→C1negative transitions remove three false-positive labels; zero correct positive labels become negative. Old/blind negative matching transitions0. Agent negative transfer is NOT_RUN, not inferred from matcher scores.

## Dataset and validation limits

New development24and independent holdout32are frozen separately with Gold hashes in evidence/b0_freeze.json. The implementation was frozen before concrete holdout inputs/Gold/results were read. Independent AI authorship and pre-freeze code review were procedurally separated; filesystem access was not cryptographically blinded. The author saw the public catalog and some old candidate-filter code; the full disclosure is in datasets/blind_manifest.json. This is model-assisted synthetic Gold, not human labeling. These inputs are now consumed regression data; no post-holdout tuning was performed.

Structural tags and source hashes do not prove natural-language feature extraction, production identity or experience utility. Neither production retrieval nor isolated injection is tested yet. All three relevance contracts pass this bounded test, but VERIFIED_EXPERIENCES=0, HUMAN_CALIBRATION=NOT_RUN, EXPERIENCE_BENEFIT=NOT_ESTABLISHED.

RED/GREEN evidence:18initial failures, independent2restriction-retention failures and1fresh-read guard failure were corrected before freeze;24coretests pass. Original evidence remains. Fresh full regression initially577PASS/1FAIL in a mocked historical crash/replay test; its isolated diagnostic passes, and the full serial recheck578PASS/0FAIL/0ERROR/0SKIP. Its intermittent root cause is not established; the safety stop refused an uncertain simulated request. The initial failure is retained, not hidden or classified as a live-model failure. Ruff check/format pass; Mypy149source files pass. New model requests/tokens/cost0.

Raw immutable run: runs/20261109_B0_01/{experiment_config,results,validation}.json plus per-cohort predictions/scores and eight_misses.json. Audit: evidence/preservation_verified.json. Next: deliver B1packet, ordinary push/ls-remote, then pause. B2/B3 require actual human review and explicit continuation. Production ACTIVE and P4 remain off.
