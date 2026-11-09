# P3-B B0/B1 human-review checkpoint

**PHASE_STATUS = WAITING_HUMAN_REVIEW.** B0 applicability engineering and B1 review material are delivered. The user explicitly requires a pause here. Actual human decisions plus an explicit continuation instruction are prerequisites for B2/B3; this checkpoint does not claim the entire P3-B phase is complete.

B0 preserves the original restrictive matcher and three candidate records. The new API measures source-bound principle relevance, carrying original restrictions and mandatory NO_EXECUTION/NO_INJECTION/Owner/HITL/idempotency obligations. It never enables retrieval into Agent context, authorizes writes or modifies business execution. See P3-B0_APPLICABILITY_REPORT.md for all eight miss paths and comparison limitations.

| Relevance cohort | Original C0 TP/FP/FN/TN | Advisory C1 TP/FP/FN/TN |
| --- | --- | --- |
| Consumed32diagnostic tasks ×3candidates | 12/0/8/76 | 20/0/0/76 |
| New development24 ×3 | 6/3/6/57 | 12/0/0/60 |
| Independently authored holdout32 ×3 | 10/0/9/77 | 19/0/0/77 |

Holdout precision/recall100%/100% are bounded structured relevance metrics, not Chinese NLU, answer accuracy or experience benefit. All three per-family relevance contracts pass; approved/VERIFIED_OFFLINE experiences remain0, with original NEEDS_REVIEW/UNREVIEWED records unchanged. No Gold or candidate text was edited. Gold is AI-authored, not human-approved, and isolation is procedural with disclosed catalog exposure. No post-holdout tuning occurred. The data are now consumed regression data.

No correct positive labels were lost. Three C0positive→C1negative development judgments remove three false positives. Agent negative transfer is NOT_RUN_WAIT_HUMAN. Zero tested advisory permission/guard conflicts does not certify safe injection. EXPERIENCE_BENEFIT=NOT_ESTABLISHED.

B1 contains exactly7saved R1 public final answers, original questions, actual tool/RAG observations, source hashes/pointers and separately folded AI opinions. PSV04/PSV13/PSV16 receive priority. No draft replaces a final answer. All human fields remain blank, not prefilled from AI judgments. Open the index, read the packet and save a CSV copy with PASS/FAIL/UNCERTAIN dimensions, reviewer identity/time and evidence-linked notes. Preserve case/query/answer identifiers. This is semantic review, not blanket experience or production approval.

The index contains actual absolute and repository-relative paths for all three deliverables:

- [Review index](P3-B1_HUMAN_REVIEW_INDEX.md)
- [Seven-answer review packet](P3-B1_HUMAN_REVIEW_PACKET.md)
- [Blank UTF-8 BOM review CSV](human_review_template.csv)

Validation: fresh548baseline PASS; final full serial578PASS/0FAIL/0ERROR/0SKIP; Ruff check and format PASS; Mypy149source files PASS; six dedicated packet tests PASS. The first full run577PASS/1FAIL in an existing mocked request-ledger crash/replay test is retained, followed by isolated1PASS and full serial578PASS. Its intermittent root cause remains undetermined; it was a simulated safety stop, not a live API incident. Initial18RED plus independent2metadata and1freshness RED checks precede fixes and freeze.

Git staging exposed automatic CSV newline normalization that would break the frozen byte hash on another checkout. A phase-local .gitattributes exception preserves the exact BOM/CRLF CSV bytes; the index now matches the manifest SHA256. The CSV contents and hashes are unchanged. The before/after check is retained in evidence/b1_csv_index_red.json and b1_csv_index_green.json.

Preservation audit verifies1,764historical tracked files,20original user files including.env, prior registry namespaces, progress prefix, candidate/source/data hashes and no actual credential match. No existing business code or historical evidence is overwritten. New HTTP requests0; billed tokens0; costUS$0. Production Active remains disabled. B2 retrieval/injection/benefit tests, B3final regression/P4planning, and P4 execution are NOT_RUN.

Recovery: feature-list.json, progress.txt, RECOVERY.md, immutable runs/20261109_B0_01, evidence/b0_freeze.json, evidence/b1_packet_validation.json and Git task checkpoints. Delivery uses normal push to authorized origin/codex/p3-experience-validation and git ls-remote; actual verification is recorded in evidence/delivery.json. Do not regenerate or overwrite the human-edited CSV or repeat paid historical requests. Wait for review results and continuation.
