"""Report immutable four-source scores and explicit baseline regressions."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_bytes())


def main():
    freeze = read(HERE / "evidence/candidate_freeze.json")
    arms = {
        name: read(HERE / f"runs/20261105_{name}_frozen_blind/results.json")["arm"]
        for name in ("C0", "C1", "C2", "C3")
    }
    configs = {
        name: read(HERE / f"runs/20261105_{name}_frozen_blind/experiment_config.json")
        for name in arms
    }
    for name, config in configs.items():
        assert config["app_hashes"] == freeze["source_snapshots"][name]["app_hashes"], name
        assert config["data"] == configs["C0"]["data"]
        assert config["eval_hashes"] == configs["C0"]["eval_hashes"]
    groups = {k: v["groups"] for k, v in arms.items()}
    source_difference = {}
    for name in ("C1", "C2", "C3"):
        a, b = configs["C0"]["app_hashes"], configs[name]["app_hashes"]
        source_difference[name] = [p for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]
    baseline = {r["case_id"]: r for r in arms["C0"]["results"]}
    transitions = {}
    for label, arm in arms.items():
        rows = {r["case_id"]: r for r in arm["results"]}
        assert set(rows) == set(baseline)
        transitions[label] = dict(
            improved=[
                c for c in rows if baseline[c]["status"] != "PASS" and rows[c]["status"] == "PASS"
            ],
            regressed=[
                dict(
                    id=c,
                    prior=baseline[c]["status"],
                    actual=rows[c]["status"],
                    reasons=rows[c]["reasons"],
                )
                for c in rows
                if baseline[c]["status"] == "PASS" and rows[c]["status"] != "PASS"
            ],
        )
    output = dict(
        status="COMPLETED_OFFLINE_FROZEN",
        groups=groups,
        source_difference=source_difference,
        transitions=transitions,
        source_freeze=freeze["candidate_commit"],
        gold_unchanged=True,
        provider="OFFLINE_SCRIPTED_NOT_REAL_LLM",
        real="NOT_RUN",
        blind_first_evaluation=True,
    )
    (HERE / "evidence/r4_metrics.json").write_bytes(
        (json.dumps(output, ensure_ascii=False, indent=2) + "\n").encode()
    )
    text = [
        "# P2-R4 fixed-M2 offline source ablation",
        "",
        f"Candidate/source/Prompt frozen at `{freeze['candidate_commit']}` before any blind execution. All160tasks per arm use the same frozen datasets, Gold/scorers, tool contracts, initial synthetic business state, M2 configuration and scripted provider. Old12corrupt cases are excluded. Distinct source snapshots: C0=0981935; C1=reviewed Context-only74b7047; C2=only Planner/Executor/prompt patch on0981935; C3=combined44f1031. Actual app/eval/data hashes are asserted against the freeze. C2 is an explicitly dirty source-control worktree with exact patch/hash, not an invented commit.",
        "",
        "| Group | C0 | C1 Context only | C2 Planner/Fallback only | C3 Combined |",
        "|---|---|---|---|---|",
    ]
    for group in groups["C0"]:
        text.append(
            "|"
            + group
            + "|"
            + "|".join(f"{groups[a][group]['passed']}/{groups[a][group]['cases']}" for a in arms)
            + "|"
        )
    text += [
        "",
        "## Per-group decision / state / cost evidence",
        "",
        "All metrics below come from unchanged per-turn tool and Goal Oracles. Argument accuracy penalizes missing calls too; it is not solely an executed wrong-ID fraction. Fresh observation additionally requires the right read in its required turn, including changed status on explicit state-event turns. This supplements rather than replaces original success standards. Latency is local end-to-end case time and includes concurrent CPU/fixture scheduling; no causal performance claim. UTF8 input bounds/scripted calls in raw group data are not billed tokens.",
        "",
        "| Arm/group | Selection | Arguments | Valid trajectory | Surplus | Tool events | Environment | Fresh reads | Mean/P95 ms |",
        "|---|---|---|---|---|---|---|---| |",
    ]
    text[-1] = "|---|---|---|---|---|---|---|---|---|"
    for label, scopes in groups.items():
        for group, m in scopes.items():
            text.append(
                f"|{label}/{group}|{m['tool_selection']:.4f}|{m['tool_arguments']:.4f}|{m['trajectory_validity']:.4f}|{m['redundant_tool_calls']}|{m['tool_calls']}|{m['environment_success']:.4f}|{m['fresh_observation_correct']}/{m['fresh_observation_required']}|{m['mean_latency_ms']:.1f}/{m['p95_latency_ms']:.1f}|"
            )
    text += [
        "",
        "## Attribution and blind discipline",
        "",
        "Old16 C0=0, Context-only=1, Planner-only=11, combined=13. Development12→14→22→27 in those arms. Blind33 C0=12, Context-only=12, Planner-only=24, combined=26. Thus most strict-task gain comes from Planner/evidence selection/argument execution, with additional Context contribution and interaction; it is not a new Memory-layer benefit. Per-case transitions are in r4_metrics.json. All original80 and seven historical references remain passing; no original80 task regression. Long-window M2 retains1/1 under all sources.",
        "",
        "Blind33was independently authored and first executed after the source freeze. No input/Gold/per-case outcome was viewed during implementation, except blind-safe aggregate static validation. It is now evaluation/regression data, not a future fresh blind set. No candidate change follows blind failures. Source/control results are not four statistically independent samples; they are paired tasks of two module changes.",
        "",
        f"Observed C3 regressions relative to C0 across all groups: `{json.dumps(transitions['C3']['regressed'],ensure_ascii=False)}`.",
        "",
        "## Retained failures and scorer limits",
        "",
        "Combined old16 retainsnu12/nu13/nu16 missing registered search_knowledge on legitimate RAG policy paths. Scores are untouched; supplemental business route/evidence judgment is separate, and semantic quality of the scripted fixed answer remains NOT_ASSESSED. Development retainsdv01(order-stage phrasing misclassified by deterministic capability proxy),dv05(negated unnecessary amount/header goal not understood by proxy),dv07(item/quantity paraphrase unsupported by proxy). These cases and earlier candidates remain in new run directories; no Gold or maxcalls changed.",
        "",
        "The seven combined blind failures are preserved with exact original reasons in r4_metrics.json. Unknown language, ambiguous references or disagreement between permitted RAG paths and tool-only observation criteria require future development/evaluation, not tuning this same held-out candidate. Zero observed hard safety violations in every group/arm; Owner/Session/HITL/idempotency and transient/freshness integration tests complement task-oracle checks. Real language/semantic judging/token/latency improvements are NOT_RUN until R5 and cannot be inferred from this fixture.",
    ]
    (HERE / "P2-R4_OFFLINE_ABLATION.md").write_bytes(("\n".join(text) + "\n").encode())
    print(
        json.dumps(
            dict(
                groups={
                    a: {k: f"{v['passed']}/{v['cases']}" for k, v in s.items()}
                    for a, s in groups.items()
                },
                regressions=transitions["C3"]["regressed"],
            )
        )
    )


if __name__ == "__main__":
    main()
