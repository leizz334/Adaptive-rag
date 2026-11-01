"""Offline P1 artifact consistency and outcome reproducibility; no business calls."""

import hashlib
import json
import statistics
import subprocess
from xml.etree import ElementTree as ET

from p1_control import ROOT, STATE, p0_check, write


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value):
    return [
        dict(
            case_id=r["case_id"],
            status=r["status"],
            reasons=r["reasons"],
            metrics={k: v for k, v in r["metrics"].items() if k != "latency_ms"},
            states=r["evidence"]["actual_order_states"],
            turns=[
                {k: v for k, v in t.items() if k != "root_run_id"} for t in r["evidence"]["turns"]
            ],
            calls=[
                {k: v for k, v in c.items() if k != "output"} for c in r["evidence"]["tool_calls"]
            ],
        )
        for r in value["results"]
    ]


def main():
    state = json.loads((STATE / "feature-list.json").read_text(encoding="utf-8"))
    p0_check(state)
    baseline = json.loads((STATE / "evidence/P1-A-baseline.json").read_text(encoding="utf-8"))
    assert all(
        digest(ROOT / "eval/dataset" / name) == row["sha256"]
        for name, row in baseline["datasets"].items()
    )
    dataset = ROOT / "eval/dataset/agent_v2.json"
    assert dataset.read_bytes() == subprocess.check_output(
        ["git", "show", "ef8f5d8:eval/dataset/agent_v2.json"]
    )
    paths = [
        STATE / "evidence" / name
        for name in ["P1-F-offline-1.json", "P1-F-offline-2.json", "P1-F-offline-off.json"]
    ]
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    assert normalized(runs[0]) == normalized(runs[1]) == normalized(runs[2])
    assert all(
        r["cases"] == 14 and r["passed"] == 12 and r["model_evaluation"] == "NOT_RUN" for r in runs
    )
    assert all(row["dataset_sha256"] == digest(dataset) for run in runs for row in run["results"])
    assert all(row["evidence"]["span_count"] == 0 for row in runs[2]["results"])
    assert all(row["evidence"]["span_count"] > 0 for row in runs[0]["results"])
    suites = ET.parse(STATE / "evidence/P1-F-pytest.xml").getroot()
    assert not list(suites.iter("failure")) and not list(suites.iter("error"))
    original = json.loads((STATE / "evidence/initial-workspace.json").read_text(encoding="utf-8"))
    for path, expected in original["preexisting_untracked_sha256"].items():
        if path != "AGENTS.md":
            assert digest(ROOT / path) == expected, path
    result = {
        "result": "PASS",
        "P0_tasks_and_evidence": "UNCHANGED_PASS",
        "legacy_datasets_unchanged": True,
        "v2_dataset_frozen_sha256": digest(dataset),
        "normalized_repeatability_and_trace_off_parity": "PASS",
        "pytest_tests": len(list(suites.iter("testcase"))),
        "scope": "synthetic offline service/SQL, not real model quality",
        "failed_cases": [
            {"id": r["case_id"], "reasons": r["reasons"]}
            for r in runs[0]["results"]
            if r["status"] != "PASS"
        ],
        "offline_metrics": {k: v for k, v in runs[0].items() if k != "results"},
        "run_hashes": {p.name: digest(p) for p in paths},
        "latency_samples_ms": {},
        "not_run": [
            "real paid model evaluation",
            "SaaS trace connectivity/credentials",
            "independent judge/human semantic calibration",
            "PostgreSQL concurrency/load",
            "uv resolver (binary unavailable)",
        ],
    }
    for label, run in zip(["on_1", "on_2", "off"], runs, strict=True):
        values = sorted(r["metrics"]["latency_ms"] for r in run["results"])
        result["latency_samples_ms"][label] = {
            "p50": statistics.median(values),
            "p95_nearest_rank": values[-1],
            "n": len(values),
            "caveat": "includes fixture setup; first run cold; not a production or isolated overhead benchmark",
        }
    scores = [t["scores"] for r in runs[0]["results"] for t in r["evidence"]["turns"]]
    args = [s["tool_argument_accuracy"] for s in scores if s["tool_argument_accuracy"] is not None]
    executed = [
        c
        for r in runs[0]["results"]
        for c in r["evidence"]["tool_calls"]
        if c["status"] == "executed"
    ]
    result["tool_metrics"] = {
        "trajectory_valid_turns": sum(s["trajectory_valid"] for s in scores),
        "turns": len(scores),
        "argument_accuracy_annotated_mean": statistics.mean(args),
        "unnecessary_calls": sum(s["unnecessary_tool_calls"] for s in scores),
        "execution_success": sum(c["success"] for c in executed) / len(executed),
        "executed_attempts": len(executed),
        "replayed": sum(
            c["status"] == "replayed"
            for r in runs[0]["results"]
            for c in r["evidence"]["tool_calls"]
        ),
    }
    extended = ROOT / "eval/dataset/agent_v2_extended.json"
    freeze = json.loads(
        (STATE / "evidence/P1-extended-dataset-freeze.json").read_text(encoding="utf-8")
    )
    assert digest(extended) == freeze["sha256"]
    ext_runs = [
        json.loads((STATE / "evidence" / name).read_text(encoding="utf-8"))
        for name in ["P1-F-extended-1.json", "P1-F-extended-2.json", "P1-F-extended-off.json"]
    ]
    assert normalized(ext_runs[0]) == normalized(ext_runs[1]) == normalized(ext_runs[2])
    assert all(r["cases"] == 80 and r["model_evaluation"] == "NOT_RUN" for r in ext_runs)
    assert all(
        row["dataset_sha256"] == digest(extended) for run in ext_runs for row in run["results"]
    )
    assert all(row["evidence"]["span_count"] == 0 for row in ext_runs[2]["results"])
    result["extended_dataset"] = {
        "cases": 80,
        "seed_cases": 14,
        "matrix_variants": 66,
        "frozen_sha256": digest(extended),
        "family_count": len({r["evidence"]["family"] for r in ext_runs[0]["results"]}),
        "metrics": {k: v for k, v in ext_runs[0].items() if k != "results"},
        "failed_cases": [
            {"id": r["case_id"], "reasons": r["reasons"]}
            for r in ext_runs[0]["results"]
            if r["status"] != "PASS"
        ],
        "repeatability_and_trace_off_parity": "PASS",
        "statistical_limit": "matrix variants in a family are correlated; not 80 independent trials",
    }
    write(STATE / "evidence/P1-final-validation.json", result)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
