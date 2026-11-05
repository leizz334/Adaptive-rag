"""Evidence integrity checks, not assertions that the Agent always succeeds."""

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs/s5_offline_fixedclock"


def read(path):
    return json.loads(path.read_bytes())


def test_actual_source_controls_preserve_required_boundaries():
    manifest = read(HERE / "evidence/s5_sources_correctedS1/manifest.json")
    freeze = read(HERE / "evidence/candidate_freeze.json")
    assert manifest["S3"]["app_hashes"] == freeze["app_hashes"]
    for arm in ("S1", "S2"):
        assert (
            manifest[arm]["app_hashes"]["app/agents/answer_evidence.py"]
            == manifest["S3"]["app_hashes"]["app/agents/answer_evidence.py"]
        )
    for name in (
        "app/agents/nodes/faithfulness.py",
        "app/guardrails/hallucination.py",
        "app/providers/deepseek.py",
    ):
        assert manifest["S2"]["app_hashes"][name] == manifest["S0"]["app_hashes"][name]
    for name in (
        "app/agents/nodes/planner.py",
        "app/retrieval/adaptive.py",
        "app/prompts/answer.py",
    ):
        assert manifest["S1"]["app_hashes"][name] == manifest["S0"]["app_hashes"][name]
    s1 = Path(manifest["S1"]["source_root"])
    text = (s1 / "app/agents/nodes/generate.py").read_text(encoding="utf-8")
    imports = [n.module for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom)]
    assert "app.agents.goals" not in imports
    assert '"generated_refusal": payload.refused' in text
    s0, s2 = (Path(manifest[a]["source_root"]) for a in ("S0", "S2"))
    base, goals = (
        (s / "app/agents/nodes/generate.py").read_text(encoding="utf-8") for s in (s0, s2)
    )
    assert (
        base[base.index("def _extractive_fallback") :]
        == goals[goals.index("def _extractive_fallback") :]
    )
    assert "LLMTruncationError" not in goals


def test_all_fixed_seed_fixtures_are_identical_and_inputs_unchanged():
    hashes, harnesses = set(), set()
    for arm in ("S0", "S1", "S2", "S3"):
        config = read(RUNS / arm / "config.json")
        validation = read(RUNS / arm / "validation.json")
        assert validation["unchanged"] is True
        assert validation["all_case_seed_hashes_match_preflight"] is True
        assert len(validation["initial_seed_hashes"]) == 214
        hashes.update(validation["initial_seed_hashes"].values())
        hashes.update(config["seed_preflight_hashes"])
        harnesses.add(config["harness_sha256"])
    assert hashes == {"3836b44bab3ea8a397a566228da2ccf0f3f3cb7c78ab5c43c6ab2799cb4e9cfc"}
    assert len(harnesses) == 1


def test_new_answer_inputs_are_actual_completed_service_observations():
    for arm in ("S0", "S1", "S2", "S3"):
        for group in ("development24", "holdout30"):
            output = RUNS / arm / group
            results = {r["case_id"]: r for r in read(output / "results.json")["results"]}
            for row in read(output / "answers.json"):
                trace = read(output / "traces" / f"{row['case_id']}.json")
                turn = trace["turns"][row["turn"]]
                assert row["final_answer"] == turn.get("response", {}).get(
                    "answer", turn.get("final_state", {}).get("final_answer", "")
                )
                assert row["actual_tool_calls"] == [
                    c
                    for c in results[row["case_id"]]["evidence"]["tool_calls"]
                    if c["turn"] == row["turn"]
                ]
                assert row["retrieved"] == [
                    chunk
                    for node in turn["nodes"]
                    for chunk in node.get("output", {}).get("retrieved_chunks", [])
                ]


def test_historical_answers_remain_unassessed_and_frozen_scorer_is_used():
    freeze = read(HERE / "evidence/candidate_freeze.json")
    for arm in ("S0", "S1", "S2", "S3"):
        config = read(RUNS / arm / "config.json")
        assert config["before"]["common_scorer"] == freeze["scorer_sha256"]
        for group in (
            "original80",
            "old16",
            "former_development30",
            "former_holdout33",
            "long_window",
        ):
            for row in read(RUNS / arm / group / "answers.json"):
                assert row["score"]["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED"
                assert row["score"]["ANSWER_COMPLETENESS"] is None
