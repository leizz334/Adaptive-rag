"""Phase continuation, atomic checkpoints and read-only verification (not Initializer)."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

STATE = Path(__file__).resolve().parent.parent
ROOT = STATE.parents[2]
PREFIX = STATE.relative_to(ROOT).as_posix() + "/"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()


def write(path, value):
    text = (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def p0_check(data):
    old = json.loads(
        subprocess.check_output(["git", "show", "3f789e1:" + PREFIX + "feature-list.json"])
    )
    assert data["tasks"][:7] == old["tasks"], "P0 state changed"
    for task in old["tasks"]:
        assert task["passes"] and task["commit_hash"]
        for f in task["evidence_files"]:
            assert (STATE / f).read_bytes() == subprocess.check_output(
                ["git", "show", task["commit_hash"] + ":" + PREFIX + f]
            )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["enable", "start", "finish", "register", "check"])
    p.add_argument("task", nargs="?")
    p.add_argument("--junit")
    p.add_argument("--commit")
    p.add_argument("--evidence", nargs="*", default=[])
    p.add_argument("--partial", action="store_true")
    a = p.parse_args()
    assert Path(sys.executable).parent.name.lower() == "adaptive-rag"
    data = json.loads((STATE / "feature-list.json").read_text(encoding="utf-8"))
    p0_check(data)
    if a.action == "enable":
        assert len(data["tasks"]) == 7, "P1 already enabled; recover instead"
        criteria = {
            "A": [
                "Immutable offline baseline with dataset/source hashes and actual pytest outcome",
                "Typed tool/trajectory/environment/result contracts and regression tests",
            ],
            "B": [
                "Configurable metadata-only spans for request/graph/LLM/retrieval/rerank/tool/memory and async/SSE",
                "Disabled/export-failure/privacy isolation tests; optional LangSmith offline payload test; cloud NOT_RUN explicitly",
            ],
            "C": [
                "Deterministic selection/argument/path/redundancy/execution/failure scoring from actual tool events",
                "Wrong arguments/tools, equivalent paths, failures and constraints covered by tests",
            ],
            "D": [
                "Isolated SQL environment with independent initial/final state and forbidden-mutation oracle",
                "Production service/tool tests cover ownership/cancel/HITL/replay/unauthorized and unrelated orders",
            ],
            "E": [
                "Five-state judge classification with errors excluded from hallucination, retrieval comparability",
                "Reusable multi-turn driver and frozen hand-labelled cases; context failures recorded without Memory changes",
            ],
            "F": [
                "Actual full regression and offline repeatability/security checks recorded",
                "P1 report/guides/metrics/limits/state/commits and safe push result; no P2 work",
            ],
        }
        for letter, cs in criteria.items():
            prev = "P0-G" if letter == "A" else "P1-" + chr(ord(letter) - 1)
            data["tasks"].append(
                dict(
                    task_id="P1-" + letter,
                    description=cs[0],
                    dependencies=[prev],
                    status="pending",
                    passes=False,
                    acceptance_criteria=cs,
                    evidence_files=[],
                    validation_results=[],
                    commit_hash=None,
                    next_action="Start when dependency-ready",
                )
            )
        data["phase"] = "P1"
        data["p1"] = {
            "base_head": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "remote": git("remote", "get-url", "origin"),
            "status": "in_progress",
            "decisions": [
                "Only P1 authorized, no production data/paid model or Memory/Experience features",
                "User AGENTS.md push policy modification and unrelated files must not be committed",
                "Manual bounded metadata spans, optional LangSmith; local raw evaluation evidence never exported",
                "Small labelled offline fixtures exercise real service; real model quality/cloud connectivity NOT_RUN",
            ],
            "push_status": "PENDING",
        }
    else:
        ts = {t["task_id"]: t for t in data["tasks"]}
        if a.action == "check":
            for t in data["tasks"][7:]:
                if t["passes"] or t["status"] == "partial_pass":
                    assert all((STATE / f).exists() for f in t["evidence_files"])
                    assert t["validation_results"]
                    if t["commit_hash"]:
                        git("cat-file", "-e", t["commit_hash"] + "^{commit}")
            print(
                json.dumps(
                    {
                        "P0": "UNCHANGED_PASS",
                        "tasks": {t["task_id"]: t["status"] for t in data["tasks"][7:]},
                        "head": git("rev-parse", "HEAD"),
                    },
                    indent=2,
                )
            )
            return
        task = ts[a.task]
        assert all(ts[d]["passes"] for d in task["dependencies"])
        if a.action == "start":
            assert not task["passes"]
            assert next(t for t in data["tasks"] if not t["passes"])["task_id"] == a.task
            task["status"] = "in_progress"
        elif a.action == "finish":
            assert task["status"] == "in_progress" and not task["passes"]
            path = STATE / a.junit
            suites = ET.parse(path).getroot()
            cases = list(suites.iter("testcase"))
            assert cases and not list(suites.iter("failure")) and not list(suites.iter("error"))
            assert all((STATE / f).is_file() for f in a.evidence)
            task.update(
                status="partial_pass" if a.partial else "completed",
                passes=not a.partial,
                evidence_files=[a.junit, *a.evidence],
                validation_results=[
                    {
                        "command": "conda run -n adaptive-rag python -B -m pytest (exact invocation in task evidence)",
                        "junit": a.junit,
                        "tests": len(cases),
                        "failures": 0,
                        "errors": 0,
                    }
                ],
            )
            if a.partial:
                task["validation_results"].append(
                    {
                        "scope": "SaaS connectivity, real-model quality and uv resolver",
                        "result": "NOT_RUN",
                        "reason": "No paid model authorization/trace credentials; uv binary unavailable",
                    }
                )
                data["p1"].update(status="PARTIAL_PASS", closed=True)
        elif a.action == "register":
            assert (task["passes"] or task["status"] == "partial_pass") and not task["commit_hash"]
            git("cat-file", "-e", a.commit + "^{commit}")
            for f in task["evidence_files"]:
                assert (STATE / f).read_bytes() == subprocess.check_output(
                    ["git", "show", a.commit + ":" + PREFIX + f]
                )
            task["commit_hash"] = a.commit
        task["next_action"] = (
            "Await P1 review; do not rerun completed tasks or start P2"
            if a.task == "P1-F"
            else "Continue next ready P1 task; after F verify/push safely and STOP"
        )
    write(STATE / "feature-list.json", data)
    progress = (STATE / "progress.txt").read_text(encoding="utf-8")
    progress += f"\nP1_CHECKPOINT action={a.action} task={a.task or 'continuation'}\nGIT_HEAD_AT_CHECK={git('rev-parse','HEAD')}\nBRANCH={git('branch','--show-current')}\n"
    if a.junit:
        progress += f"VALIDATION_JUNIT={a.junit}\nFILES={', '.join(a.evidence)}\n"
    if a.commit:
        progress += f"DELIVERY_COMMIT={a.commit}\n"
    progress += (
        "NEXT_ACTION=Continue authorized P1 in task order; after F STOP for P1 review. No P2-P4.\n"
    )
    write(STATE / "progress.txt", progress)
    print(
        json.dumps({"action": a.action, "task": a.task, "head": git("rev-parse", "HEAD")}, indent=2)
    )


if __name__ == "__main__":
    main()
