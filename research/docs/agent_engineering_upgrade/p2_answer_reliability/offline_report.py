"""Aggregate immutable S5 evidence without retuning data, Agent or evaluator."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs/s5_offline_fixedclock"
ARMS = {"S0": "S0", "S1": "S1", "S2": "S2", "S3": "S3"}


def read(path):
    return json.loads(path.read_bytes())


def write_new(path, text):
    with path.open("x", encoding="utf-8", newline="\n") as out:
        out.write(text)


def main():
    aggregate, failures, comparisons, matrices = {}, {}, {}, {}
    lines = [
        "# P2-S5 offline source controls",
        "",
        "All results below are ENGINEERING_FIXTURE observations of real production service/nodes with fixed synthetic ScriptedProvider, M2, fixtures and the frozen common answer evaluator. The provider emits JSON tool facts and predetermined judgments; these are not real LLM language, semantic judgment, paid model quality or production latency claims. Gold enters only the evaluator after service execution. Network connections/DNS and external tracing were disabled. No main candidate, scorer or Gold changes followed holdout outcomes.",
        "",
        "Four actual application sources were bound before imports. S0 is e74f01d (the old44f1031 application); S1 is reviewed1c6b506 answer/Judge/provider recovery plus trusted-refusal metadata and the shared frozen pure renderer; S2 is e74f01d with only frozen goals/planner/adaptive/answer prompt and goal-specific Generate branches; S3 is frozen37a7e47 application. S2 retains the original exception/extractive fallback, Judge/provider and offline tail. The renderer is shared in S1/S2/S3, so these are mechanism bundles with a dependency, not disjoint-file factorial effects. Exact app hashes and patches are in evidence/s5_sources_correctedS1/manifest.json and evidence/s5_sources/{S0,S2,S3}.patch.",
        "",
        "Two experiment-control defects were corrected with all original runs preserved. The first S1 patch failed to add generated_refusal because its source substring did not match; detached S1 metadata was corrected and re-executed in runs/s5_offline/S1_corrected. Initial fixtures also seeded order timestamps from the wall clock, so initial controls were not fully identical. The final tables use complete reruns in runs/s5_offline_fixedclock/{S0,S1,S2,S3} with the corrected S1 source and app.services.seed.utcnow scoped to naive UTC2026-11-05T00:00:00. Two-environment preflights per source and every case's initial orders/items/products hash agree across all arms:3836b44bab3ea8a397a566228da2ccf0f3f3cb7c78ab5c43c6ab2799cb4e9cfc. Session/generated output IDs are not part of that seed hash. No tool has a separate runtime eligibility clock in these frozen sources. These are disclosed infrastructure repairs after first holdout consumption; the frozen candidate, scorer, data and annotations were unchanged.",
        "",
        "## Original strict tool, trajectory and state oracle",
        "",
        "| Arm | old80 | old16 | former dev30 | former hold33 | long window | new dev24 | new hold30 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, directory in ARMS.items():
        summary = read(RUNS / directory / "summary.json")
        assert read(RUNS / directory / "validation.json")["unchanged"]
        groups = summary["groups"]
        lines.append(
            "| "
            + arm
            + " | "
            + " | ".join(
                f"{groups[g]['passed']}/{groups[g]['cases']}"
                for g in (
                    "original80",
                    "old16",
                    "former_development30",
                    "former_holdout33",
                    "long_window",
                    "development24",
                    "holdout30",
                )
            )
            + " |"
        )
        aggregate[arm], failures[arm], matrices[arm] = (
            {},
            {},
            read(RUNS / directory / "fault_matrix.json"),
        )
        for group, metric in groups.items():
            rows = read(RUNS / directory / group / "answers.json")
            coverage = [
                r["score"]["ANSWER_COMPLETENESS"]
                for r in rows
                if r["score"].get("ANSWER_COMPLETENESS") is not None
            ]
            counts = {
                field: dict(Counter(r["score"].get(field, "NOT_ASSESSED") for r in rows))
                for field in (
                    "OVERALL_TASK_SUCCESS",
                    "ANSWER_FACTUAL_CORRECTNESS",
                    "ANSWER_FAITHFULNESS",
                    "ABSTENTION_CORRECTNESS",
                )
            }
            strict = dict(metric)
            aggregate[arm][group] = dict(
                strict=strict,
                answer_turns=len(rows),
                answer_counts=counts,
                mean_required_subgoal_coverage=mean(coverage) if coverage else None,
            )
            failures[arm][group] = dict(
                strict=metric["failure_cases"],
                answer=[
                    dict(
                        case_id=r["case_id"],
                        turn=r["turn"],
                        score=r["score"],
                        final_answer=r["final_answer"],
                    )
                    for r in rows
                    if r["score"]["OVERALL_TASK_SUCCESS"] != "PASS"
                ],
            )
    lines += [
        "",
        "Original80 stays80/80 in every arm; no historical drop is hidden. Old16 remains13/16 with strict failures nu12,nu13,nu16 retained in every arm. They are not regraded as semantic success. All old datasets and long-window lack answer Gold: every historical final answer is explicitly NOT_ASSESSED by the new answer scorer. All hard safety violation counts are zero under the unchanged oracle.",
        "",
        "## New frozen answer annotations",
        "",
        "Turn counts, rather than case counts, are used below. Coverage measures annotated required subgoals. P/F/U means PASS/FAIL/NOT_ASSESSED and never promotes unknown semantics to PASS.",
        "",
        "| Arm | Split | Turns | Overall P/F/U | Factual P/F/U | Faithfulness P/F/U | Mean coverage |",
        "|---|---|---:|---|---|---|---:|",
    ]
    for arm in ARMS:
        for group in ("development24", "holdout30"):
            item = aggregate[arm][group]

            def triple(field, item=item):
                counts = item["answer_counts"][field]
                return "/".join(str(counts.get(k, 0)) for k in ("PASS", "FAIL", "NOT_ASSESSED"))

            lines.append(
                f"| {arm} | {group} | {item['answer_turns']} | {triple('OVERALL_TASK_SUCCESS')} | {triple('ANSWER_FACTUAL_CORRECTNESS')} | {triple('ANSWER_FAITHFULNESS')} | {item['mean_required_subgoal_coverage']:.3f} |"
            )
    lines += [
        "",
        "Environment is the unchanged case-final state oracle and is labeled as such for each answer turn. Tool success is computed from actual per-turn original oracle failures: required calls, arguments, trajectory, unexpected errors/failures, pending/refusal and confirmation constraints. Answer evidence comes only from actual recorded calls and retrieved node chunks. Tool/state success can coexist with incomplete or unassessed answers.",
        "",
        "## Detailed source metrics",
        "",
        "| Arm | Split | Tool selection | Arguments | Trajectory | Extra calls | Environment | Mean/p95 ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    def number(value):
        return "N/A" if value is None else f"{value:.3f}"

    for arm in ARMS:
        for group, item in aggregate[arm].items():
            m = item["strict"]
            lines.append(
                f"| {arm} | {group} | {number(m['tool_selection'])} | {number(m['tool_arguments'])} | {number(m['trajectory_validity'])} | {m['redundant_tool_calls']} | {number(m['environment_success'])} | {m['mean_latency_ms']:.1f}/{m['p95_latency_ms']:.1f} |"
            )
    lines += [
        "",
        "Latency includes local instrumentation/SQLite and concurrent source processes; it is descriptive fixture runtime, not an isolated production performance comparison. The initial inherited benchmark summary incorrectly defaulted scripted_calls/input to zero because unchanged oracle rows lacked those optional fields. Final fixedclock summaries derive those fields from actual captured fixture provider calls instead. Input_utf8_bound is an engineering byte bound, not measured model tokens. Paid calls/tokens are zero; real model evaluation is NOT_RUN.",
        "",
        "## Changes and remaining failures",
        "",
    ]
    baseline = ARMS["S0"]
    for arm in ("S1", "S2", "S3"):
        comparisons[arm] = {}
        for group in aggregate[arm]:
            old = {
                r["case_id"]: r for r in read(RUNS / baseline / group / "results.json")["results"]
            }
            new = {
                r["case_id"]: r for r in read(RUNS / ARMS[arm] / group / "results.json")["results"]
            }
            before = {
                (r["case_id"], r["turn"]): r for r in read(RUNS / baseline / group / "answers.json")
            }
            after = {
                (r["case_id"], r["turn"]): r
                for r in read(RUNS / ARMS[arm] / group / "answers.json")
            }
            answer_changes = [
                dict(case_id=k[0], turn=k[1], before=before[k]["score"], after=after[k]["score"])
                for k in before
                if before[k]["score"] != after[k]["score"]
            ]
            comparisons[arm][group] = dict(
                strict_improved=[
                    k for k in old if old[k]["status"] != "PASS" and new[k]["status"] == "PASS"
                ],
                strict_regressed=[
                    k for k in old if old[k]["status"] == "PASS" and new[k]["status"] != "PASS"
                ],
                answer_changes=answer_changes,
                coverage_regressed=[
                    dict(
                        case_id=k[0],
                        turn=k[1],
                        before=before[k]["score"]["ANSWER_COMPLETENESS"],
                        after=after[k]["score"]["ANSWER_COMPLETENESS"],
                    )
                    for k in before
                    if before[k]["score"].get("ANSWER_COMPLETENESS") is not None
                    and after[k]["score"]["ANSWER_COMPLETENESS"]
                    < before[k]["score"]["ANSWER_COMPLETENESS"]
                ],
            )
    for split in ("development24", "holdout30"):
        m = failures["S3"][split]
        lines.append(
            f"S3 {split} strict failing cases: "
            + ", ".join(f"{r['id']} ({'; '.join(r['reasons'])})" for r in m["strict"])
            + "."
        )
    all_regressions = [
        (arm, group, r)
        for arm, groups in comparisons.items()
        for group, changes in groups.items()
        for r in changes["strict_regressed"]
    ]
    lines += [
        "",
        f'Strict case regressions from S0: {all_regressions or "none"}. Per-turn answer changes, coverage regressions and every failure/unknown final text are retained in evidence/s5_aggregate.json. The new holdout was first evaluated after candidate/scorer/data freeze and is now consumed regression evidence. No production, scorer or Gold update was made in response. These limited regex/fact contracts have no human semantic calibration; unannotated wording and open policy/clarification semantics remain NOT_ASSESSED.',
        "",
        "## Separate evaluator and injected failure controls",
        "",
        "The four answer-only counterexamples are evaluator calibration, not Agent tasks: complete, omitted amount, false operation and unsupported promise use identical actual observations. Per-source evaluator_counterexamples.json retains exact outcomes. The 10-row Judge/Generate matrix per source covers two-business-fact and unrelated-retrieval evidence crossed with truncation exception, length marker, API error, malformed JSON and schema error. This is mock failure injection, not paid API evidence. Raw verdict/error category, final answer and call counts are retained in fault_matrix.json; Judge unknown is never rewritten to supported.",
        "",
    ]
    for arm in ARMS:
        item = next(
            r
            for r in matrices[arm]["results"]
            if r["evidence"] == "two_business_facts" and r["fault"] == "truncated_exception"
        )
        lines.append(
            f"{arm} Judge-truncation fallback: {item['faithfulness'].get('final_answer', '(no replacement)')}"
        )
    lines += [
        "",
        "S0/S2 retain old Judge failure recovery by construction; S1/S3 preserve the observed amount and shipment together with explicit limits. S2 successful-response goal completion is separate from S1 error recovery. The standalone length-marker mock can reach a node with a partial payload, while the actual provider normally rejects structured length termination first; it is a defensive boundary test, not a measured historical provider incidence.",
        "",
        "## Reproduction and preservation",
        "",
        "Use Conda adaptive-rag Python. For a fresh checkout without the explicitly named controls, run:",
        "",
        "```powershell",
        "python research/docs/agent_engineering_upgrade/p2_answer_reliability/source_controls.py",
        "```",
        "",
        "Then run from each source root with the common harness absolute path (replace paths and use a new unique output directory; existing results are preserved):",
        "",
        "```powershell",
        '$phase = "D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability/research/docs/agent_engineering_upgrade/p2_answer_reliability"',
        'python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s0 --label S0 --output "$phase/runs/s5_reproduction/S0"',
        'python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s1 --label S1 --output "$phase/runs/s5_reproduction/S1"',
        'python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2s-s2 --label S2 --output "$phase/runs/s5_reproduction/S2"',
        'python "$phase/offline.py" --source-root D:/Code/Adaptive-rag/.worktrees/p2-answer-reliability --label S3 --output "$phase/runs/s5_reproduction/S3"',
        "```",
        "",
        "The source builder now asserts S1 refusal metadata was inserted. For this existing preserved initial experiment only, its exact repair command was source_controls.py --correct-s1, followed by the S1 command with label/output S1_corrected. Fixed-clock preflights used the four commands with --preflight-only and evidence/s5_preflight/{arm} outputs; final runs used runs/s5_offline_fixedclock/{arm}. No existing control directory is removed or overwritten by the builder.",
        "",
        "Each config/validation records before/after application, Prompt, source eval, common answer scorer, data and Gold hashes. All final validation unchanged flags are true. All 214 cases per arm were executed; raw original score rows retain every failure. New development/holdout and old failing/selected cases retain full actual node/database/pending traces; all cases retain actual final answers and call evidence. No secret environment file or external trace was accessed, and no paid call was made. S6 real pairs remain separate authorized work.",
    ]
    aggregate_path = HERE / "evidence/s5_aggregate.json"
    write_new(
        aggregate_path,
        json.dumps(
            dict(
                arms=aggregate,
                failures=failures,
                comparisons_from_S0=comparisons,
                initial_s1_retained="runs/s5_offline/S1",
                final_s1="runs/s5_offline_fixedclock/S1",
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    write_new(HERE / "P2-S5_OFFLINE_ABLATION.md", "\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                arm: {
                    split: aggregate[arm][split]["answer_counts"]["OVERALL_TASK_SUCCESS"]
                    for split in ("development24", "holdout30")
                }
                for arm in ARMS
            }
        )
    )


if __name__ == "__main__":
    main()
