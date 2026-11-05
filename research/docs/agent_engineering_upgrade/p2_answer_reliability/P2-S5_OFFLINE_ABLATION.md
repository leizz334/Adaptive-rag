# P2-S5 offline source controls

All results below are ENGINEERING_FIXTURE observations of real production service/nodes with fixed synthetic ScriptedProvider, M2, fixtures and the frozen common answer evaluator. The provider emits JSON tool facts and predetermined judgments; these are not real LLM language, semantic judgment, paid model quality or production latency claims. Gold enters only the evaluator after service execution. Network connections/DNS and external tracing were disabled. No main candidate, scorer or Gold changes followed holdout outcomes.

Four actual application sources were bound before imports. S0 is e74f01d (the old44f1031 application); S1 is reviewed1c6b506 answer/Judge/provider recovery plus trusted-refusal metadata and the shared frozen pure renderer; S2 is e74f01d with only frozen goals/planner/adaptive/answer prompt and goal-specific Generate branches; S3 is frozen37a7e47 application. S2 retains the original exception/extractive fallback, Judge/provider and offline tail. The renderer is shared in S1/S2/S3, so these are mechanism bundles with a dependency, not disjoint-file factorial effects. Exact app hashes and patches are in evidence/s5_sources_correctedS1/manifest.json and evidence/s5_sources/{S0,S2,S3}.patch.

Two experiment-control defects were corrected with all original runs preserved. The first S1 patch failed to add generated_refusal because its source substring did not match; detached S1 metadata was corrected and re-executed in runs/s5_offline/S1_corrected. Initial fixtures also seeded order timestamps from the wall clock, so initial controls were not fully identical. The final tables use complete reruns in runs/s5_offline_fixedclock/{S0,S1,S2,S3} with the corrected S1 source and app.services.seed.utcnow scoped to naive UTC2026-11-05T00:00:00. Two-environment preflights per source and every case's initial orders/items/products hash agree across all arms:3836b44bab3ea8a397a566228da2ccf0f3f3cb7c78ab5c43c6ab2799cb4e9cfc. Session/generated output IDs are not part of that seed hash. No tool has a separate runtime eligibility clock in these frozen sources. These are disclosed infrastructure repairs after first holdout consumption; the frozen candidate, scorer, data and annotations were unchanged.

## Original strict tool, trajectory and state oracle

| Arm | old80 | old16 | former dev30 | former hold33 | long window | new dev24 | new hold30 |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | 80/80 | 13/16 | 27/30 | 26/33 | 1/1 | 12/24 | 12/30 |
| S1 | 80/80 | 13/16 | 27/30 | 26/33 | 1/1 | 12/24 | 12/30 |
| S2 | 80/80 | 13/16 | 30/30 | 33/33 | 1/1 | 23/24 | 22/30 |
| S3 | 80/80 | 13/16 | 30/30 | 33/33 | 1/1 | 23/24 | 22/30 |

Original80 stays80/80 in every arm; no historical drop is hidden. Old16 remains13/16 with strict failures nu12,nu13,nu16 retained in every arm. They are not regraded as semantic success. All old datasets and long-window lack answer Gold: every historical final answer is explicitly NOT_ASSESSED by the new answer scorer. All hard safety violation counts are zero under the unchanged oracle.

## New frozen answer annotations

Turn counts, rather than case counts, are used below. Coverage measures annotated required subgoals. P/F/U means PASS/FAIL/NOT_ASSESSED and never promotes unknown semantics to PASS.

| Arm | Split | Turns | Overall P/F/U | Factual P/F/U | Faithfulness P/F/U | Mean coverage |
|---|---|---:|---|---|---|---:|
| S0 | development24 | 40 | 0/20/20 | 0/0/40 | 0/0/40 | 0.179 |
| S0 | holdout30 | 41 | 0/25/16 | 2/0/39 | 2/0/39 | 0.280 |
| S1 | development24 | 40 | 0/20/20 | 0/0/40 | 0/0/40 | 0.179 |
| S1 | holdout30 | 41 | 0/25/16 | 2/0/39 | 2/0/39 | 0.280 |
| S2 | development24 | 40 | 15/2/23 | 17/0/23 | 15/0/25 | 0.500 |
| S2 | holdout30 | 41 | 1/17/23 | 4/0/37 | 4/1/36 | 0.488 |
| S3 | development24 | 40 | 15/2/23 | 17/0/23 | 15/0/25 | 0.500 |
| S3 | holdout30 | 41 | 1/17/23 | 4/0/37 | 4/1/36 | 0.488 |

Environment is the unchanged case-final state oracle and is labeled as such for each answer turn. Tool success is computed from actual per-turn original oracle failures: required calls, arguments, trajectory, unexpected errors/failures, pending/refusal and confirmation constraints. Answer evidence comes only from actual recorded calls and retrieved node chunks. Tool/state success can coexist with incomplete or unassessed answers.

## Detailed source metrics

| Arm | Split | Tool selection | Arguments | Trajectory | Extra calls | Environment | Mean/p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| S0 | original80 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 480.9/729.3 |
| S0 | old16 | 0.903 | 0.889 | 0.903 | 0 | 1.000 | 477.3/827.1 |
| S0 | former_development30 | 0.962 | 0.938 | 0.942 | 4 | 1.000 | 503.1/806.7 |
| S0 | former_holdout33 | 0.880 | 0.819 | 0.852 | 3 | 0.970 | 518.3/775.3 |
| S0 | development24 | 0.762 | 0.604 | 0.675 | 8 | 1.000 | 463.2/701.4 |
| S0 | holdout30 | 0.549 | 0.485 | 0.488 | 14 | 0.933 | 454.1/766.1 |
| S0 | long_window | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 866.6/866.6 |
| S1 | original80 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 486.2/719.4 |
| S1 | old16 | 0.903 | 0.889 | 0.903 | 0 | 1.000 | 477.7/863.4 |
| S1 | former_development30 | 0.962 | 0.938 | 0.942 | 4 | 1.000 | 501.4/802.8 |
| S1 | former_holdout33 | 0.880 | 0.819 | 0.852 | 3 | 0.970 | 516.1/741.0 |
| S1 | development24 | 0.762 | 0.604 | 0.675 | 8 | 1.000 | 465.7/729.7 |
| S1 | holdout30 | 0.549 | 0.485 | 0.488 | 14 | 0.933 | 453.6/781.4 |
| S1 | long_window | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 786.4/786.4 |
| S2 | original80 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 482.6/708.8 |
| S2 | old16 | 0.903 | 0.889 | 0.903 | 0 | 1.000 | 468.9/837.1 |
| S2 | former_development30 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 501.5/815.6 |
| S2 | former_holdout33 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 512.0/717.0 |
| S2 | development24 | 1.000 | 1.000 | 0.975 | 1 | 1.000 | 460.2/716.5 |
| S2 | holdout30 | 0.817 | 0.809 | 0.756 | 4 | 0.933 | 454.0/654.5 |
| S2 | long_window | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1211.5/1211.5 |
| S3 | original80 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 484.9/724.8 |
| S3 | old16 | 0.903 | 0.889 | 0.903 | 0 | 1.000 | 480.1/877.3 |
| S3 | former_development30 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 505.8/798.9 |
| S3 | former_holdout33 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 516.2/750.9 |
| S3 | development24 | 1.000 | 1.000 | 0.975 | 1 | 1.000 | 459.0/719.0 |
| S3 | holdout30 | 0.817 | 0.809 | 0.756 | 4 | 0.933 | 449.5/674.0 |
| S3 | long_window | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1174.2/1174.2 |

Latency includes local instrumentation/SQLite and concurrent source processes; it is descriptive fixture runtime, not an isolated production performance comparison. The initial inherited benchmark summary incorrectly defaulted scripted_calls/input to zero because unchanged oracle rows lacked those optional fields. Final fixedclock summaries derive those fields from actual captured fixture provider calls instead. Input_utf8_bound is an engineering byte bound, not measured model tokens. Paid calls/tokens are zero; real model evaluation is NOT_RUN.

## Changes and remaining failures

S3 development24 strict failing cases: PSD06 (turn:0:trajectory_invalid).
S3 holdout30 strict failing cases: PSH13 (turn:0:trajectory_invalid), PSH18 (turn:2:missing_tool; turn:2:trajectory_invalid; turn:2:wrong_arguments), PSH19 (turn:0:pending_mismatch; turn:0:trajectory_invalid; turn:1:missing_confirmation_reference; turn:1:missing_response; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:unexpected_error:INVALID_REQUEST; turn:1:wrong_arguments; turn:2:trajectory_invalid; wrong_audit_actions; wrong_count:refunds; wrong_final_status:ORD10001), PSH20 (turn:0:pending_mismatch; turn:1:missing_confirmation_reference; turn:1:missing_response; turn:1:missing_tool; turn:1:trajectory_invalid; turn:1:unexpected_error:INVALID_REQUEST; turn:1:wrong_arguments; wrong_audit_actions; wrong_count:returns), PSH25 (turn:0:missing_tool; turn:0:trajectory_invalid; turn:0:wrong_arguments), PSH26 (turn:0:missing_tool; turn:0:trajectory_invalid; turn:0:wrong_arguments), PSH28 (turn:0:missing_tool; turn:0:pending_mismatch; turn:0:trajectory_invalid; turn:0:wrong_arguments), PSH30 (turn:0:missing_tool; turn:0:trajectory_invalid; turn:0:wrong_arguments).

Strict case regressions from S0: none. Per-turn answer changes, coverage regressions and every failure/unknown final text are retained in evidence/s5_aggregate.json. The new holdout was first evaluated after candidate/scorer/data freeze and is now consumed regression evidence. No production, scorer or Gold update was made in response. These limited regex/fact contracts have no human semantic calibration; unannotated wording and open policy/clarification semantics remain NOT_ASSESSED.

## Separate evaluator and injected failure controls

The four answer-only counterexamples are evaluator calibration, not Agent tasks: complete, omitted amount, false operation and unsupported promise use identical actual observations. Per-source evaluator_counterexamples.json retains exact outcomes. The 10-row Judge/Generate matrix per source covers two-business-fact and unrelated-retrieval evidence crossed with truncation exception, length marker, API error, malformed JSON and schema error. This is mock failure injection, not paid API evidence. Raw verdict/error category, final answer and call counts are retained in fault_matrix.json; Judge unknown is never rewritten to supported.

S0 Judge-truncation fallback: 订单 ORD8080 的物流状态：运输中。
S1 Judge-truncation fallback: 以下是本次工具结果可确认的信息：
订单 ORD8080 当前订单状态：已支付。
订单 ORD8080 总金额：156.78元（人民币）。
订单 ORD8080 的物流状态：运输中。
其余所需结论暂时无法可靠确认，请补充信息或转人工；上述事实不代表其他操作已完成。
S2 Judge-truncation fallback: 订单 ORD8080 的物流状态：运输中。
S3 Judge-truncation fallback: 以下是本次工具结果可确认的信息：
订单 ORD8080 当前订单状态：已支付。
订单 ORD8080 总金额：156.78元（人民币）。
订单 ORD8080 的物流状态：运输中。
其余所需结论暂时无法可靠确认，请补充信息或转人工；上述事实不代表其他操作已完成。

S0/S2 retain old Judge failure recovery by construction; S1/S3 preserve the observed amount and shipment together with explicit limits. S2 successful-response goal completion is separate from S1 error recovery. The standalone length-marker mock can reach a node with a partial payload, while the actual provider normally rejects structured length termination first; it is a defensive boundary test, not a measured historical provider incidence.

## Reproduction and preservation

Use Conda adaptive-rag Python. For a fresh checkout without the explicitly named controls, run:

```powershell
python research/docs/agent_engineering_upgrade/p2_answer_reliability/source_controls.py
```

Then run from each source root with the common harness absolute path (replace paths and use a new unique output directory; existing results are preserved):

```powershell
$phase = "D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability/research/docs/agent_engineering_upgrade/p2_answer_reliability"
python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s0 --label S0 --output "$phase/runs/s5_reproduction/S0"
python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s1 --label S1 --output "$phase/runs/s5_reproduction/S1"
python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s2 --label S2 --output "$phase/runs/s5_reproduction/S2"
python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability --label S3 --output "$phase/runs/s5_reproduction/S3"
```

The source builder now asserts S1 refusal metadata was inserted. For this existing preserved initial experiment only, its exact repair command was source_controls.py --correct-s1, followed by the S1 command with label/output S1_corrected. Fixed-clock preflights used the four commands with --preflight-only and evidence/s5_preflight/{arm} outputs; final runs used runs/s5_offline_fixedclock/{arm}. No existing control directory is removed or overwritten by the builder.

Each config/validation records before/after application, Prompt, source eval, common answer scorer, data and Gold hashes. All final validation unchanged flags are true. All 214 cases per arm were executed; raw original score rows retain every failure. New development/holdout and old failing/selected cases retain full actual node/database/pending traces; all cases retain actual final answers and call evidence. No secret environment file or external trace was accessed, and no paid call was made. S6 real pairs remain separate authorized work.

## Case-level answer rollup

The original answer table counts turns. Separately, a whole scenario is FAIL if any required turn fails, PASS only if every turn passes, otherwise NOT_ASSESSED. `case_metrics.py` derives this from unchanged per-turn results; no new scoring or labels are introduced. Baseline S0/S1 Development:0PASS/17FAIL/7NOT_ASSESSED; Holdout:0PASS/21FAIL/9NOT_ASSESSED. Candidate S2/S3 Development:10PASS/2FAIL/12NOT_ASSESSED; Holdout:1PASS/13FAIL/16NOT_ASSESSED. All case IDs, goal omissions and unknown-goal counts are in evidence/s5_case_metrics.json. Thus strict22/30 does not mean22 complete semantic tasks; only one held-out scenario is fully verified under this conservative annotated contract. No broad answer generalization claim is supported by the offline fixture.
