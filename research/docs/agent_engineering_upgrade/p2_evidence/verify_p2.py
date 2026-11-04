"""Verify P2 archived evidence offline; no application startup or model requests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from eval.contracts import ToolCall  # noqa: E402
from eval.memory_ablation import long_window_case  # noqa: E402
from eval.multiturn import load_scenarios  # noqa: E402
from eval.tool_scoring import score_tools  # noqa: E402

HERE = Path(__file__).resolve().parent
STATE = HERE.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def matches_text_hash(path, digest):
    data = path.read_bytes()
    # Earlier artifacts were committed with LF but some root files retain their
    # original Windows CRLF. Accept checkout newline normalization, not content changes.
    return digest in {
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
    }


def main():
    gate = read(HERE / "P2-A-analysis.json")
    for name, digest in gate["immutable_artifact_sha256"].items():
        assert matches_text_hash(ROOT / name, digest), name
    config = read(HERE / "P2-E-experiment-config.json")
    for name, digest in config["original_gold_and_score_files_sha256"].items():
        assert matches_text_hash(ROOT / name, digest), name
    assert (
        hashlib.sha256((HERE / "heldout_reference.json").read_bytes()).hexdigest()
        == config["heldout_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "eval/memory_ablation.py").read_bytes()).hexdigest()
        == config["ablation_source_sha256"]
    )
    original, _ = load_scenarios(ROOT / "eval/dataset/agent_v2_extended.json")
    heldout, _ = load_scenarios(HERE / "heldout_reference.json")
    scenarios = {s.id: s for s in [*original, *heldout, long_window_case()]}
    compared = 0
    snapshots = []
    for name in ("P2-E-results.json", "P2-E-reviewed-results.json"):
        value = read(HERE / name)
        assert value["status"] == "COMPLETED_OFFLINE_ONLY"
        assert (
            value["real_model_evaluation"] == "NOT_RUN"
            and value["paid_api_calls"] == value["paid_tokens"] == 0
        )
        assert len(value["arms"]) == 8
        snapshot = {}
        for arm in value["arms"]:
            assert len(arm["results"]) == len(scenarios) == 93
            for case in arm["results"]:
                gold = scenarios[case["case_id"]]
                calls = [ToolCall.model_validate(c) for c in case["evidence"]["tool_calls"]]
                for index, turn in enumerate(case["evidence"]["turns"]):
                    scores = score_tools(
                        [c for c in calls if c.turn == index], gold.turns[index].trajectory
                    )
                    assert scores == turn["scores"], (arm["mode"], case["case_id"], index)
                    compared += 1
                snapshot[(arm["provider"], arm["mode"], case["case_id"])] = (
                    case["status"],
                    case["reasons"],
                    case["metrics"]["environment_state_correct"],
                )
            g = arm["groups"]
            assert g["original80"]["passed"] == (66 if arm["mode"] == "M0" else 73)
            assert g["original7"]["passed"] == (0 if arm["mode"] == "M0" else 7)
            assert g["heldout12"]["passed"] == (2 if arm["mode"] == "M0" else 3)
            assert g["long_window"]["passed"] == 0
            assert g["long_window"]["environment_success"] == (
                1 if arm["mode"] in {"M2", "M3"} else 0
            )
            assert all(not group["safety_violations"] for group in g.values())
        snapshots.append(snapshot)
    assert (
        snapshots[0] == snapshots[1]
    ), "Review fixes must not silently rewrite initial experiment outcomes"
    baseline = json.loads(
        subprocess.check_output(
            [
                "git",
                "show",
                gate["source_baseline"]
                + ":research/docs/agent_engineering_upgrade/feature-list.json",
            ],
            cwd=ROOT,
        ).decode("utf-8")
    )
    current = read(STATE / "feature-list.json")
    assert {k: v for k, v in current.items() if k != "p2"} == baseline
    for name in ("P1_REPORT.md", "P0_AUDIT_REPORT.md", "audits/memory_context.md"):
        relative = "research/docs/agent_engineering_upgrade/" + name
        before = subprocess.check_output(
            ["git", "show", gate["source_baseline"] + ":" + relative], cwd=ROOT
        )
        assert (ROOT / relative).read_bytes().replace(b"\r\n", b"\n") == before.replace(
            b"\r\n", b"\n"
        )
    suite = ET.parse(HERE / "P2-final-pytest.xml").getroot().find("testsuite")
    assert (
        suite is not None
        and suite.get("tests") == "247"
        and suite.get("failures") == suite.get("errors") == "0"
    )
    assert current["p2"]["paid_model_calls_authorized"] is False
    print(
        json.dumps(
            {
                "status": "PASS",
                "immutable_prior_artifacts": len(gate["immutable_artifact_sha256"]),
                "heldout_cases": len(heldout),
                "offline_snapshots": 2,
                "arms_per_snapshot": 8,
                "tool_turn_scores_recomputed": compared,
                "unchanged_scenario_outcomes_across_review_fix": True,
                "full_tests": 247,
                "new_paid_requests": 0,
                "new_paid_tokens": 0,
                "p1_status": "PARTIAL_PASS",
                "real_baseline_status": "PARTIAL",
            }
        )
    )


if __name__ == "__main__":
    main()
