"""Offline artifact verification only; never imports or invokes an LLM provider."""

import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import mean

RUN = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[6]
STATE = ROOT / "research/docs/agent_engineering_upgrade"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    config = read(RUN / "experiment_config.json")
    result = read(RUN / "results.json")
    rows = read(RUN / "requests.json")
    summary, analysis = result["summary"], result["analysis"]
    assert len(rows) == config["max_http_attempts"] == 80
    assert all(r["http_status"] == 200 and not r.get("failure") for r in rows)
    assert sum(r["usage"]["total_tokens"] for r in rows) == summary["total_tokens"] == 58342
    assert summary["total_tokens"] <= config["max_accounted_tokens"]
    assert all(
        r["usage"]["total_tokens"] == r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"]
        for r in rows
    )
    assert all(
        r["max_tokens"] <= config["max_output_tokens_per_request"] and r.get("temperature", 0) == 0
        for r in rows
    )
    assert {r["model_reported"] for r in rows} == {"deepseek-flash"}
    assert set(r["case_id"] for r in result["results"]) == set(config["selected_case_ids"])
    valid = [r for r in result["results"] if r["status"] in {"PASS", "FAIL"}]
    assert len(valid) == summary["valid_cases"] == 9
    assert sum(r["status"] == "PASS" for r in valid) == summary["passed"] == 2
    assert summary["task_success_rate"] == 2 / 9
    refs = [r for r in valid if r["case_id"] in config["reference_case_ids"]]
    assert len(refs) == summary["reference_evaluated"] == 7
    assert all(r["status"] == "FAIL" for r in refs)
    assert summary["reference_correct"] == 0
    assert summary["environment_success"] == mean(
        r["metrics"]["environment_state_correct"] for r in valid
    )
    turns = [t for r in valid for t in r["evidence"]["turns"]]
    assert len(turns) == summary["tool_selection_turns"] == 17
    assert summary["tool_selection_accuracy"] == mean(
        t["scores"]["tool_selection_accuracy"] for t in turns
    )
    assert summary["tool_argument_accuracy"] == mean(
        t["scores"]["tool_argument_accuracy"]
        for t in turns
        if t["scores"]["tool_argument_accuracy"] is not None
    )
    latencies = sorted(r["metrics"]["latency_ms"] for r in valid)
    assert analysis["valid_case_mean_latency_ms"] == mean(latencies)
    assert analysis["valid_case_p95_latency_ms"] == latencies[math.ceil(0.95 * len(latencies)) - 1]
    interrupted = [r for r in result["results"] if r["status"] == "ERROR"]
    assert len(interrupted) == 1 and interrupted[0]["case_id"] == "greeting"
    assert interrupted[0]["api_request_count"] == 0
    assert sum(r["status"] == "NOT_RUN" for r in result["results"]) == 5
    assert result["status"] == "PARTIAL" and result["stop_reason"] == "request_budget_exhausted"
    assert not summary["baseline_reproducible"]
    assert all(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in config["frozen_files"].items()
    )
    assert (
        hashlib.sha256((STATE / "real_llm_baseline/evaluate_real.py").read_bytes()).hexdigest()
        == config["evaluation_harness_sha256"]
    )
    original = json.loads(
        subprocess.check_output(
            [
                "git",
                "show",
                config["baseline_git_head"]
                + ":research/docs/agent_engineering_upgrade/feature-list.json",
            ],
            cwd=ROOT,
        ).decode("utf-8")
    )
    current = read(STATE / "feature-list.json")
    assert {k: v for k, v in current.items() if k != "real_llm_baseline_retries"} == original
    for name in (
        "BASELINE_REPORT.md",
        "failed_cases.md",
        "requests.json",
        "results.json",
        "experiment_config.json",
        "validation.json",
    ):
        relative = "research/docs/agent_engineering_upgrade/real_llm_baseline/" + name
        old = subprocess.check_output(
            ["git", "show", config["baseline_git_head"] + ":" + relative], cwd=ROOT
        )
        assert (ROOT / relative).read_bytes().replace(b"\r\n", b"\n") == old.replace(b"\r\n", b"\n")
    suite = ET.parse(RUN / "validation-pytest.xml").getroot().find("testsuite")
    assert suite.get("tests") == "31" and suite.get("failures") == suite.get("errors") == "0"
    print(
        "PASS: actual request/token totals, original scores/denominators, budget exclusions, latency, 181 frozen P1 hashes, prior failed run/state, executed harness hash, 31-test evidence."
    )


if __name__ == "__main__":
    main()
