# P2-Q execution plan

Authorized scope: QA real paired validation; QB nine diagnostic failures; QC independent Planner/Fallback optimization; QD attribution and regression. No P3/P4. Original P1/P2 remain PARTIAL_PASS and all old evidence is immutable.

Baseline: `c45f509f5e4260c34818df9bf48f2807dd1338b4`, confirmed pushed `origin/codex/p2-memory-context`. Isolated branch `codex/p2-quality`, worktree `.worktrees/p2-quality`. Root user modifications and ignored credentials stay untouched. Conda environment: `adaptive-rag`.

1. QA: freeze source/data/prompt/config hashes; test a durable request ledger and replay transport; one connectivity probe and one three-mode pilot; evaluate the seven frozen reference cases plus three controls with interleaved M0/M1/M2. All modes use identical current P2 application source and settings except Memory. Independent synthetic SQLite per group, no external tracing. Persist each request before dispatch and each response before downstream evaluation. Ambiguous interrupted requests stop rather than replay network calls.
2. QB: inspect each of hr01–hr09 through actual traces. Initial byte inspection found literal ASCII question marks in the frozen old heldout input. Preserve the original inputs/Gold/scores, investigate dataset corruption before attributing failure to Memory. No rule may infer intended meaning from corrupted text. Only evidence-backed generic Memory defects justify a code change. Old12 are now diagnostic regression, not blind tests.
3. QC: freeze C0 offline evidence at fixed M2; establish whether Owner fallback and long-window shipment reads are necessary. Test minimal changes independently of Memory. Preserve permission checks, live reads, HITL and transient-error behavior. Keep Gold unchanged. Real C0/C1 only if a complete pair fits the same global budget; otherwise NOT_RUN.
4. QD: freeze final implementation before revealing independently authored new cases. Evaluate original P2, Memory-only, Planner-only and combined source variants; where no Memory change is justified, report the corresponding variants as identical rather than inventing a gain. Run all pytest, Ruff lint/format, Mypy, P1 compatibility and full80/old12/unseen/long-window controls. Preserve all failures and regression counts.

Each task receives acceptance evidence, state update and separate commit. Completed commit hashes are recorded in the following checkpoint. Normal push only after remote/branch/worktree review. Stop after P2-Q.

## Shared paid budget and pricing

Global maximum across QA and any subsequent real retests: 350 HTTP attempts, 300,000 accounted tokens, estimated US$3, concurrency 1, no automatic retries. Reserve conservatively before every request; missing usage is charged its full conservative reservation. Forecast before every new group; stop and retain partial pairs rather than expand the budget. An in-flight request without durable response is uncertain and must never be automatically repeated.

Official pricing checked 2026-11-04: https://api-docs.deepseek.com/quick_start/pricing/ . `deepseek-flash` peak cache-miss input $0.30/M, output $1.20/M; use peak rates and no cache discounts. At the most expensive token rate 300,000 tokens cost $0.36, conditional on these published rates and complete accounting. This is an estimate, not a provider invoice guarantee. Alias/backend model may change; retain response model metadata. Temperature is fixed identically in all real arms; existing structured-output budgets and Planner strategy are held constant.

Only synthetic fixture prompts/results enter local request checkpoints. Never persist Authorization, API keys, hidden reasoning content or real user/order data. Offline and paid results are always reported separately; historical 9/15, 2/9, 0/7, 58,342-token baseline is reference only.

## Reproducibility limits

API outputs can vary despite temperature zero. The old heldout's corrupted language prevents semantic generalization claims. Original seven are development verification. New unseen cases remain authored checks rather than statistical population estimates. Preserve raw outcomes even when fallback recovers from model errors.
