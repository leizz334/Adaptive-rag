# P2 offline ablation — real-model arms NOT_RUN

The original frozen datasets/Gold/scorers and all real/P1 baseline evidence remain unchanged. No paid requests were authorized in P2; paid calls/tokens0. Do not compare these offline percentages as causal gains over real DeepSeek2/9.

Two deterministic providers exercise the same production service/graph/tools/repositories and original P1 scorer: OFFLINE_RULE uses existing rule paths; OFFLINE_SCRIPTED consumes actual Intent/Router/Planner/Generate/Judge prompts and constructs fixed valid responses from current query/tool data, without Gold or network. Its judge always returns a scripted supported verdict: this does not measure semantic faithfulness, hallucination or real model generalization. All scripted input sizes are conservative UTF-8 estimates, never billed tokens.

## Controls and held-out discipline

Original80 includes the seven historical reference failures. Twelve independent reference cases were authored by a separate agent and frozen at SHA256 `f1200034a4048b20768ba2097bc408097f760dd7974ae8fe2ed093a15343fefc` before Memory implementation. The implementer did not view them during B/C tuning. First evaluated in E, failures retained. A development long-window case was also predeclared; it is not held-out.

The identical P2-A reliability repair is held constant across M0–M3. Planner policy/skill definitions are unchanged. M0 is no-history with reliability-only repair; M1 recent session history; M2 M1+incremental summary; M3 M2+synthetic consented verified-request preference prototype (public M3 disabled). A fresh branch review independently identified policy-routing/window-loading regressions, reproduced RED and fixed in an isolated commit before a NEW final output. No held-out sample or Gold was tuned; first results remain `p2_evidence/P2-E-results.json`, final replay is `P2-E-reviewed-results.json` at source40d8622.

All offline arms retain the same production per-node temperature/cap schedule (Generate0.2, other relevant nodes0.0); scripted responses are deterministic and ignore sampling. The old real run forced0.0 globally and is a different experimental control, another reason no direct real-model gain comparison is valid.

## Task and reference results

Rule and scripted providers have identical task/selection/argument/environment results:

| Dataset / criterion | M0 | M1 | M2 | M3 synthetic |
|---|---:|---:|---:|---:|
| Original80 Task Success |66/80 (82.5%)|73/80 (91.25%)|73/80 (91.25%)|73/80 (91.25%)|
| Original7 reference Task Success |0/7|7/7|7/7|7/7|
| Original80 Tool Selection (turn mean)|95.76%|100%|100%|100%|
| Original80 Argument Accuracy (labelled turn mean)|92.93%|100%|100%|100%|
| Original80 environment + observations|77/80 (96.25%)|80/80|80/80|80/80|
| Independent held-out Task Success |2/12|3/12|3/12|3/12|
| Independent held-out selection / arguments |68.75% /59.09%|71.875% /59.09%|71.875% /59.09%|71.875% /59.09%|
| Independent held-out environment + observations |9/12|9/12|9/12|9/12|
| Development long-window Task Success |0/1|0/1|0/1|0/1|
| Development long-window fresh state/observation |0/1|0/1|1/1|1/1|

The original seven are development evidence, not an independent generalization claim. M2/M3 recover the old entity/live observation after it leaves the window, but the unchanged Planner additionally calls track_shipment beyond the development case's strict allowed trajectory. Task stays FAIL; no Gold was relaxed. Original80 retains seven known ownership-fallback redundant-trajectory failures, not new forbidden mutations.

**Nine of twelve held-out cases still fail** (missing required read/wrong reference arguments, three missing fresh changed-state observations). The heuristic reference selector is limited; it does not demonstrate broad semantic pronoun resolution. These failures remain explicit TODO/quality gates. No extra paid baseline was run, and no future Memory/Planner change was made to improve these scores.

## Cost and latency accounting

Scripted responses are local Python fixtures, not model API calls. For original80, each scripted arm uses521fixture responses. Conservative complete message-input bounds: M0=1185055, M1/M2=1253027, M3=1260587 UTF-8-based units. These counts include repeated calls across many synthetic scenarios and are NOT tokens charged by DeepSeek. Selecting context increases some input estimates; no claim of reduced API cost is supported.

Long-window scripted calls: M0=28, M1=23 (clarification avoids the final five responses), M2/M3=28 (correct live read requires those five). No summarization call is added. M2 long-window input estimate53139 vs M1=40264; this is a correctness/cost tradeoff in the fixture, not a real performance improvement.

Per-mode, per-dataset actual offline case wall-clock mean/P95 (nearest rank) and input/call estimates are saved in each arm's groups and summarized in P2_REPORT.md / P2-E-metrics.json. Timings include fixture/DB initialization and local CPU scheduling; they are not remote-model latency/SLA or a fair warm-runtime overhead estimate. P2 real M0/M1/M2/M3 token/latency/task/reference/JSON-quality comparisons are all **NOT_RUN**.

## Reproduction and limitations

Use Conda adaptive-rag. `python -B -m eval.memory_ablation --output <NEW_PATH.json>` is offline-only and forbids socket connections. Existing results cannot be overwritten by the command. Initial/final source commits and ablation/Gold/scorer hashes are archived. Original success reasons and per-turn scores/tool evidence are retained, not rewritten as aggregate passes. Independent policy/how-to and M1window100 review regressions are separate from held-out cases.

P1 PARTIAL_PASS and real baseline PARTIAL remain unchanged. Public authentication, cross-instance concurrency, production workload, summary semantic fidelity and independently calibrated real-model judging are not established. All authorized offline work stops at P2; no P3/P4 or new paid calls.
