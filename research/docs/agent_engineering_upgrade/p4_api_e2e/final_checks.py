"""Read-only preservation/source controls and local style gates for P4-A."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_api_e2e.manage import (
    BASE,
    HERE,
    REVIEW,
    ROOT,
    STATE,
    git,
    save,
    sha,
)

APP_CHANGES = {"app/main.py", "app/agents/goals.py", "app/api/routes/chat.py"}


def read(path):
    return json.loads(path.read_bytes())


def gates():
    outputs = []
    for args in (
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
    ):
        result = subprocess.run(
            [sys.executable, "-B", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            check=False,
        )
        outputs.append(
            dict(
                command=[sys.executable, "-B", *args],
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    target = HERE / "evidence/final_style.json"
    assert not target.exists(), "Preserve prior validation"
    save(target, outputs)
    assert all(r["exit_code"] == 0 for r in outputs)


def audit():
    inventory = read(HERE / "evidence/preservation.json")
    changed = [p for p, h in inventory["prior_files"].items() if sha(ROOT / p) != h]
    assert set(changed) == APP_CHANGES
    assert sha(ROOT / REVIEW) == inventory["edited_review_sha256"]
    user = Path(inventory["user_root"])
    assert all(sha(user / p) == h for p, h in inventory["root_user_files"].items())
    before = json.loads(
        subprocess.check_output(
            ["git", "show", f"{BASE}:research/docs/agent_engineering_upgrade/feature-list.json"],
            cwd=ROOT,
        )
    )
    state = read(STATE / "feature-list.json")
    phase = state.pop("p4_api_e2e")
    assert not phase["active_enabled"] and not phase["paid_calls_allowed"]
    assert state == before
    old_progress = subprocess.check_output(
        ["git", "show", f"{BASE}:research/docs/agent_engineering_upgrade/progress.txt"], cwd=ROOT
    )
    assert (STATE / "progress.txt").read_bytes().startswith(old_progress)
    run = HERE / "runs/20261110_A2_final_01"
    matrix = read(run / "matrix_results.json")
    assert (
        matrix["scenarios"],
        matrix["passed"],
        matrix["failed"],
        matrix["blocked"],
        matrix["http_requests"],
    ) == (42, 41, 0, 1, 55)
    assert [r["case"] for r in matrix["outcomes"] if r["status"] == "BLOCKED"] == [
        "trusted_identity_authentication"
    ]
    manifest = read(run / "startup.json")
    assert (
        manifest["provider"] == "ControlledLLM"
        and manifest["memory"] == "M2"
        and manifest["experience_mode"] == "off"
    )
    assert (
        manifest["actual_engine_url"] == "sqlite+aiosqlite:///" + (run / "app.sqlite3").as_posix()
    )
    assert not manifest["paid_api"] and not manifest["external_tracing"]
    process = read(run / "process.json")
    assert all(sha(ROOT / p) == h for p, h in process["application_sha256"].items())
    assert (
        sha(HERE / "worker.py") == process["worker_sha256"]
        and sha(HERE / "test_real_http.py") == process["matrix_source_sha256"]
    )
    cleanup = read(run / "owned_cleanup.json")
    assert (
        cleanup["exit_code"] == 0
        and cleanup["graceful_request"]
        and cleanup["application_sources_unchanged"]
    )
    captures = read(run / "shutdown.json")["capture_errors"]
    assert set(captures) == {"trace_failure_isolation"} and captures["trace_failure_isolation"] > 0
    events = [
        json.loads(line)
        for line in (run / "events.jsonl").read_text(encoding="utf8").splitlines()
        if line
    ]
    assert not any(row["kind"] == "outbound_denied" for row in events)
    assert not any(
        s["status"] == "running" for e in events if e["kind"] == "spans" for s in e["spans"]
    )
    owned = []
    for directory in sorted((HERE / "runs").iterdir()):
        path = directory / "owned_cleanup.json"
        if path.exists():
            entry = read(path)
            assert entry["exit_code"] is not None and entry["stopped_only_owned_process"]
            owned.append(dict(run=directory.name, **entry))
    suite = ET.parse(HERE / "evidence/a2_full_pytest.xml").getroot().find("testsuite")
    assert (
        suite.get("tests") == "671"
        and suite.get("skipped") == "1"
        and suite.get("failures") == suite.get("errors") == "0"
    )
    final = ET.parse(HERE / "evidence/a2_http_final.xml").getroot().find("testsuite")
    assert (
        final.get("tests") == "42"
        and final.get("skipped") == "1"
        and final.get("failures") == final.get("errors") == "0"
    )
    legacy = read(HERE / "runs/20261110_A2_legacy_01/results.json")
    assert not legacy["regressions"]
    secrets = []
    for line in (user / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            v = v.strip().strip("\"'")
            if len(v) >= 12 and any(t in k.upper() for t in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                secrets.append(v.encode())
    paths = [
        p
        for p in HERE.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".sqlite3", ".log"}
    ]
    assert not any(s in p.read_bytes() for s in secrets for p in paths)
    staged = git("diff", "--cached", "--name-only").splitlines()
    assert REVIEW not in staged
    result = dict(
        baseline=BASE,
        historical_files_checked=len(inventory["prior_files"]),
        allowed_application_changes=changed,
        historical_evidence_and_gold_changes=0,
        root_user_files_preserved=len(inventory["root_user_files"]),
        edited_review_preserved=True,
        old_registry_namespaces_preserved=True,
        progress_prefix_preserved=True,
        new_worktree_created=False,
        final_run=run.name,
        matrix=dict(total=42, passed=41, failed=0, blocked=1, requests=55),
        full_pytest=dict(passed=670, failed=0, blocked_skip=1),
        all_owned_children_finished=owned,
        normal_capture_failures=0,
        deliberate_capture_error_counts=captures,
        final_application_worker_and_matrix_sources_unchanged=True,
        outbound_nonloopback_attempts=0,
        paid_model_calls=0,
        actual_secret_matches=0,
        legacy_regressions=[],
        experience_active=False,
        P4_B_started=False,
        phase_status="PARTIAL_PASS",
    )
    save(HERE / "evidence/final_audit.json", result)
    save(
        HERE / "evidence/final_source_freeze.json",
        dict(
            head=git("rev-parse", "HEAD"),
            application=process["application_sha256"],
            worker_sha256=process["worker_sha256"],
            matrix_sha256=process["matrix_source_sha256"],
            initial_A1_source_commit="56cca47596db5c9679a99abde4be8cb4ca98a509",
            final_run=run.name,
            original_review_sha256=inventory["edited_review_sha256"],
        ),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "all_owned_children_finished"}))


if __name__ == "__main__":
    gates()
    audit()
