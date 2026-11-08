# P2-S6 real source pairs

Preparation and mock tests send no real HTTP. This runner is a new experiment;
it never opens an earlier P2-Q/P2-R run directory. In particular, the old pending
194/109 requests must remain untouched and must never be replayed here.

The runner reuses the unchanged P2-Q durable public-response transport and P2-R
timing/source-binding helpers through absolute imports. Their hashes, current
answer scorer, frozen instrumentation, candidate freeze, and this runner are
bound into the immutable configuration. Importing the runner or running
`_imports` does not read a developer env file. Explicit `prepare` may read the
supplied env file to fingerprint configuration; it performs no network calls.

Hard limits include the probe: 350 HTTP attempts, 300,000 accounted tokens,
estimated US$3, concurrency one, and at most 24 HTTP attempts per scenario arm.
Every generation gets one HTTP attempt with temperature zero and at most 1024
output tokens. The single probe has a 32-token cap. Under the supplied published
peak prices, even 300,000 all-output tokens would estimate US$0.36; the separate
US$3 guard remains enforced. Estimates are not invoices. Missing or inconsistent
usage charges the complete UTF-8 request byte count plus safety allowance and
the reserved output cap. Reasoning/hidden content, credentials, and error bodies
are excluded from persisted provider responses.

The parent verified [official pricing](https://api-docs.deepseek.com/quick_start/pricing/)
on 2026-11-05: input cache miss US$0.30/M, output US$1.20/M, without cache
discounts. The configured model is preserved; no model, thinking, endpoint, or
application setting is changed to fit the experiment. Published alias details
do not independently verify backend weights. Thinking may consume the small
output budget and cause truncation; that outcome is retained.

The candidate Python app source must exactly match `evidence/candidate_freeze.json` (app source
commit `37a7e47d241175c0af9a110686ef6bf90c621c62`); R0 must be clean at
`e74f01db65fb9f3df929cdf5932919e1f10e453e`. Current metadata HEADs are recorded at
preparation. The freeze contains 128 Python hashes; the full source snapshots also
contain four skill JSON contracts. Non-Python app contracts must exactly match
the clean R0 baseline, including the same file set; changed, missing, or added
contracts are rejected. All 132 files remain in the immutable source fingerprint.
Metadata-only checkpoint commits afterward are allowed only while
all frozen runtime source/helper/scorer/data bytes remain identical. Shared
evaluator, knowledge, seed, settings, and call-site caps must match. Actual
signature defaults are recorded separately, including intentional Judge changes.

Only PSD03, PSD05, PSD08, and PSD10 are predeclared development cases. Six holdout
IDs are selected using SHA256(`P2S-20261105` + ID); no query, Gold, or outcome is
used for selection. Source order alternates by case, one repetition each. The
first development source pair completes before any later case. Partial stopping
at a hard budget is valid and must be reported with its real denominator.

Every arm runs in a fresh source-bound process. `BusinessEnvironment` supplies
isolated in-memory SQLite and M2; no production DSN is passed to it. External
tracing is disabled. The shared seed clock freezes imported business-clock
aliases and captured SQLAlchemy timestamp defaults. Initial seed tables are
captured, hashed, and compared across the pair; a mismatch stops continuation.

Frozen `instrumented.py` remains byte-for-byte unchanged. The explicit paid
worker scopes its offline-network context to `nullcontext` so the configured
provider can run, and extends only the captured extra-field allowlist with
Judge/error/completeness metadata. The same scope is tested with MockTransport.
No product graph, policy, tool permission, ownership, or Gold input changes occur.

Before running, commit the reviewed harness and complete the parent's S5
checkpoint. Use a fresh run directory. These PowerShell commands are examples
for the authorized future run, not a record that a paid run occurred:

```powershell
$taskPython = 'D:/MiniAnaconda3/envs/adaptive-rag/python.exe'
$taskRoot = 'D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability'
$taskPhase = "$taskRoot/research/docs/agent_engineering_upgrade/p2_answer_reliability"
$taskHarness = "$taskPhase/real_pairs.py"
$taskRun = "$taskPhase/runs/20261105_S6_pairs_02"
& $taskPython $taskHarness prepare --run-dir $taskRun --env-file 'D:/Code/Adaptive-rag/.env' --r0-root 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality' --r1-root $taskRoot --dev-dataset "$taskPhase/datasets/development.json" --dev-answers "$taskPhase/datasets/development_answers.json" --blind-dataset "$taskPhase/datasets/holdout.json" --blind-answers "$taskPhase/datasets/holdout_answers.json" --input-price 0.30 --output-price 1.20 --pricing-url 'https://api-docs.deepseek.com/quick_start/pricing/' --pricing-verified-date '2026-11-05'
& $taskPython $taskHarness probe --run-dir $taskRun --source-root 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality' --variant R0
& $taskPython $taskHarness pilot --run-dir $taskRun
& $taskPython $taskHarness summary --run-dir $taskRun
```

Review pilot evidence/accounting before issuing `run` for the remaining frozen
groups. `resume` is the same bounded coordinator; neither command changes the
selection or budgets. Never rerun `prepare` against an existing run. A completed
group returns `ALREADY_COMPLETED`. After a crash, only matching durable completed
responses can be replayed; this incurs no new HTTP attempts. Any PENDING row
stops all execution for manual reconciliation. Connect/timeout/cancellation,
including BaseException during response-body reading, records elapsed time and
leaves the reservation pending. No automatic resend or retry is allowed.

`requests.json` reserves before dispatch and checkpoints whitelisted public
responses before provider parsing. `captures/*.json` preserves actual final
answers, node states, tool observations, and initial/final/per-turn DB snapshots
before answer Gold is loaded for scoring. A scoring/results-write crash therefore
does not lose the paid responses. Source/config/request hash drift stops replay.

Scoring uses the frozen current `eval/answer_scoring.py` via an absolute module
loader after the Agent finishes. Raw old tool/environment driver output remains
available with its original `NOT_RUN` default. New evidence metadata explicitly
records the configured real provider; actual tool/environment results and answer
scores remain separate. Unsupported extra clauses stay `NOT_ASSESSED` and
`semantic_human_calibration` remains `NOT_RUN`; there is no same-model semantic
self-judge or claim of general natural-language accuracy.

Mock validation (use a fresh basetemp path if the system temp ACL is unavailable):

```powershell
& $taskPython -m pytest "$taskPhase/test_p2s_real_pairs.py" -q --tb=short --basetemp "$taskRoot/.pytest_cache/p2s-real-fresh"
```

## V2.1 continuation after the pilot scorer correction

Run02's original answers, scores, journal, and exact V2.0 source copies remain
immutable. The pilot used 11 HTTP attempts and 10,003 reported/accounted tokens,
estimated US$0.0045516. These are spent global budget, never a fresh allowance.
The old holdout is consumed; it must not be described as fresh validation.

The new explicit freeze is `evidence/candidate_freeze_v21.json`. An alternate
freeze requires `--budget-parent-run`; it cannot silently create a zero-spend
budget. The continuation reads the direct parent's config/requests/results,
requires complete responses with valid usage and one successful stored P2S_OK
probe, and validates provider/settings/environment/model/pricing/source controls.
Only `eval/answer_scoring.py` may differ within the app/eval/knowledge source map.
Original Q/R5/instrumentation helpers must remain unchanged. No env file is read
when validating the ancestor itself; explicit preparation still fingerprints its
configured env through source workers.

Completed parent request dictionaries are copied once, unchanged, at the start
of the new journal. Every request's pre-dispatch check revalidates parent artifact
hashes and the exact inherited prefix. Pending rows, missing/inconsistent usage,
duplicate sequences, parent mutation, missing rows, or control conflicts stop the
run. Inherited rows count toward all 350/300k/US$3 global limits. They cannot be
replayed by a fresh planned group. Direct ancestry is supported; nested ancestry
is rejected for explicit audit rather than inferred or deduplicated speculatively.

Run03 reuses the successful physical probe by a hashed parent-results reference;
it must not issue another probe or replay PSD03. Its paid plan contains only six
fresh PSV IDs selected from exactly 24 IDs by
SHA256(`P2S-V21-20261105` + ID), with alternating source order. Development paths
may remain fingerprinted in the config, but no development cases enter this paid
plan. Previously captured development answers can be rescored locally; missing
old captures are not invented or filled by paid calls.

The V2.1 adapter uses exactly same-turn tool calls and that turn's failure-prefix
for TOOL_SUCCESS. Actual retrieved chunks come from the captured final state.
ENVIRONMENT_SUCCESS remains the original final case-wide environment oracle;
it is not a per-turn DB-state claim. Original V2.0 scores keep their original
case-wide tool/cumulative-evidence meaning. The new adapter does not rewrite old
scores, old Gold, captured answers, or raw driver output. Open semantics remain
NOT_ASSESSED without independent semantic calibration.

After the parent freezes and commits the corrected scorer/new validation data:

```powershell
$taskParentRun = "$taskPhase/runs/20261105_S6_pairs_02"
$taskBaseline = 'D:/Code/Adaptive-rag/.worktrees/p2-agent-quality'
$taskRun = "$taskPhase/runs/20261105_S6_pairs_03"
& $taskPython $taskHarness prepare --run-dir $taskRun --freeze-file "$taskPhase/evidence/candidate_freeze_v21.json" --budget-parent-run $taskParentRun --env-file 'D:/Code/Adaptive-rag/.env' --r0-root $taskBaseline --r1-root $taskRoot --dev-dataset "$taskPhase/datasets/development.json" --dev-answers "$taskPhase/datasets/development_answers.json" --blind-dataset "$taskPhase/datasets/validation_holdout_v21.json" --blind-answers "$taskPhase/datasets/validation_holdout_v21_answers.json" --input-price 0.30 --output-price 1.20 --pricing-url 'https://api-docs.deepseek.com/quick_start/pricing/' --pricing-verified-date '2026-11-05'
& $taskPython $taskHarness summary --run-dir $taskRun
```

Prepare prints selected IDs/group order and inherited spend only, never Gold.
Subsequent `run-group`, `pilot`, or `run` workers resolve the frozen file path from
the new config before loading helpers. No new probe command is needed. Parent
review of the fresh plan and global accounting precedes further paid commands.
