"""Read-only final evidence gate, including unchanged original scoring contracts."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from eval.contracts import ToolCall
from eval.memory_ablation import long_window_case
from eval.multiturn import load_scenarios
from eval.tool_scoring import score_tools

ROOT = Path(__file__).resolve().parents[4]
QUALITY = Path(__file__).resolve().parent
BASE = "c45f509f5e4260c34818df9bf48f2807dd1338b4"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    preserved = read(QUALITY / "preservation.json")["historical_files"]
    for path, expected in preserved.items():
        raw = (ROOT / path).read_bytes()
        # Legacy root checkout retained CRLF; the isolated checkout uses the
        # existing .gitattributes LF policy. Root raw bytes are checked below.
        assert (
            sha(ROOT / path) == expected
            or hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == expected
        ), path
    state_path = "research/docs/agent_engineering_upgrade/feature-list.json"
    baseline = json.loads(
        subprocess.check_output(["git", "show", BASE + ":" + state_path], cwd=ROOT)
    )
    current = read(ROOT / state_path)
    assert {k: v for k, v in current.items() if k != "p2_quality"} == baseline
    progress_path = "research/docs/agent_engineering_upgrade/progress.txt"
    previous = subprocess.check_output(["git", "show", BASE + ":" + progress_path], cwd=ROOT)
    assert (
        (ROOT / progress_path)
        .read_bytes()
        .replace(b"\r\n", b"\n")
        .startswith(previous.replace(b"\r\n", b"\n"))
    )
    root_user = read(QUALITY / "root_user_preservation.json")
    for name, expected in root_user["files"].items():
        assert sha(Path(root_user["root"]) / name) == expected, name
    if (QUALITY / "root_historical_preservation.json").exists():
        for name, expected in read(QUALITY / "root_historical_preservation.json").items():
            assert sha(Path(root_user["root"]) / name) == expected, name
    freeze = read(QUALITY / "reviewed_implementation_freeze.json")
    assert all(sha(ROOT / p) == value for p, value in freeze["source"].items())
    assert sha(QUALITY / "new_unseen.json") == freeze["unseen_sha256"]
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", BASE, "--", "app", "eval"], cwd=ROOT, text=True
    ).splitlines()
    assert set(changed) == {
        "app/agents/nodes/executor.py",
        "app/agents/nodes/planner.py",
        "app/prompts/planner.py",
    }
    cases = []
    for path in (
        ROOT / "eval/dataset/agent_v2_extended.json",
        ROOT / "research/docs/agent_engineering_upgrade/p2_evidence/heldout_reference.json",
        QUALITY / "new_unseen.json",
    ):
        rows, _ = load_scenarios(path)
        cases += rows
    cases.append(long_window_case())
    by_id = {c.id: c for c in cases}
    compared = 0
    for directory in sorted((QUALITY / "runs").iterdir()):
        if not directory.is_dir() or not (directory / "results.json").exists():
            continue
        raw = read(directory / "results.json")
        result_groups = [g for arm in raw.get("arms", []) for g in arm["results"]] + raw.get(
            "groups", []
        )
        for result in result_groups:
            case = by_id[result["case_id"]]
            for turn in result["evidence"]["turns"]:
                calls = [
                    ToolCall.model_validate(c)
                    for c in result["evidence"]["tool_calls"]
                    if c["turn"] == turn["turn"]
                ]
                assert score_tools(calls, case.turns[turn["turn"]].trajectory) == turn["scores"]
                compared += 1
    qa = QUALITY / "runs/20261104_QA_real_01"
    requests = read(qa / "requests.json")
    assert len(requests) == 194 and sum(r["status"] == "PENDING" for r in requests) == 1
    assert sum((r.get("usage") or {}).get("total_tokens", 0) for r in requests) == 151933
    assert len({(r["group"], r["sequence"]) for r in requests}) == len(requests)
    config = read(qa / "experiment_config.json")
    assert sha(QUALITY / "real.py") == config["harness_sha256"]
    assert all(r.get("http_status") == 200 for r in requests if r["status"] == "RESPONSE")
    assert all(g["actual_http_responses"] > 0 for g in read(qa / "model_provenance.json")["groups"])
    suite = ET.parse(QUALITY / "reviewed_full_pytest.xml").getroot().find("testsuite")
    assert (
        suite is not None
        and suite.get("tests") == "274"
        and suite.get("failures") == suite.get("errors") == "0"
    )
    # Exact secret scan compares in memory and never prints the credential.
    from app.config.settings import Settings

    key = (
        Settings(_env_file=Path(root_user["root"]) / ".env")
        .deepseek_api_key.get_secret_value()
        .encode()
    )
    assert key
    for path in QUALITY.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".md", ".json", ".xml"}:
            assert key not in path.read_bytes(), path.name
    output = dict(
        status="PASS",
        historical_files_preserved=len(preserved),
        root_user_files_preserved=len(root_user["files"]),
        tool_turn_scores_recomputed=compared,
        pytest=274,
        source_freeze=True,
        old_state_unchanged=True,
        gold_scorers_unchanged=True,
        secret_scan="PASS",
        real_http_attempts=194,
        real_reported_tokens=151933,
        pending_uncertain=1,
        paid_replay="BLOCKED_UNTIL_MANUAL_RECONCILIATION",
        quality_status="PARTIAL_PASS",
    )
    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main()
