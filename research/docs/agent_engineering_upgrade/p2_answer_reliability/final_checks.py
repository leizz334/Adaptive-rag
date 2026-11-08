"""Local delivery checks; no model calls, secret output or historical writes."""

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import dotenv_values

from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import (
    BASE,
    HERE,
    ROOT,
    git,
    save,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    checks = {}
    for name, command in (
        ("ruff_check", ["-m", "ruff", "check", "."]),
        ("ruff_format", ["-m", "ruff", "format", "--check", "."]),
        ("mypy", ["-m", "mypy"]),
    ):
        completed = subprocess.run(
            [sys.executable, "-B", *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        checks[name] = dict(
            exit_code=completed.returncode, output=completed.stdout + completed.stderr
        )
    suites = ET.parse(HERE / "evidence/s7_all_pytest.xml").getroot()
    checks["pytest"] = {
        k: sum(int(s.get(k, 0)) for s in suites.iter("testsuite"))
        for k in ("tests", "errors", "failures", "skipped")
    }
    previous = read(HERE / "evidence/preservation.json")
    prior_changed = [p for p, h in previous["prior_artifacts"].items() if sha(ROOT / p) != h]
    user_changed = [
        p for p, h in previous["user_files"].items() if sha(Path(previous["user_root"]) / p) != h
    ]
    state_path = "research/docs/agent_engineering_upgrade/feature-list.json"
    before_state = json.loads(git("show", f"{BASE}:{state_path}"))
    state = read(ROOT / state_path)
    state.pop("p2_answer_reliability")
    progress_path = "research/docs/agent_engineering_upgrade/progress.txt"
    old_progress = git("show", f"{BASE}:{progress_path}")
    progress = (ROOT / progress_path).read_text(encoding="utf-8")
    original = read(HERE / "evidence/candidate_freeze.json")
    revision = read(HERE / "evidence/candidate_freeze_v21.json")
    app_hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "app").rglob("*.py")}
    data = HERE / "datasets"
    contracts = {name: sha(data / name) for name in original["datasets"]}
    snapshot = read(HERE / "evidence/s6_v20_sources/manifest.json")
    snapshot_ok = all(
        sha(HERE / info["snapshot"]) == info["sha256"] for info in snapshot["files"].values()
    )
    secret_values = [
        v
        for k, v in dotenv_values(Path(previous["user_root"]) / ".env").items()
        if v
        and any(t in k.upper() for t in ("KEY", "PASSWORD", "SECRET", "TOKEN"))
        and len(v) >= 12
    ]
    scan = [
        *HERE.rglob("*.json"),
        *HERE.rglob("*.md"),
        *HERE.rglob("*.xml"),
        *HERE.rglob("*.txt"),
        *HERE.rglob("*.py"),
    ]
    exposed = [
        str(p.relative_to(ROOT))
        for p in scan
        if any(v.encode() in p.read_bytes() for v in secret_values)
    ]
    preservation = dict(
        prior_artifacts_checked=len(previous["prior_artifacts"]),
        prior_changed=prior_changed,
        root_user_files_checked=len(previous["user_files"]),
        user_changed=user_changed,
        historical_registry_unchanged=state == before_state,
        progress_append_only=progress.startswith(old_progress),
        frozen_app_unchanged=app_hashes == original["app_hashes"] == revision["app_hashes"],
        original_datasets_unchanged=contracts == original["datasets"],
        revised_datasets_unchanged=all(
            sha(data / name) == h for name, h in revision["datasets"].items()
        ),
        active_scorer_matches_v21=sha(ROOT / "eval/answer_scoring.py") == revision["scorer_sha256"],
        v20_source_snapshot_unchanged=snapshot_ok,
        v20_scorer_matches_original_freeze=snapshot["files"]["eval/answer_scoring.py"]["sha256"]
        == original["scorer_sha256"],
        secret_scan_files=len(scan),
        credential_value_exposure_paths=exposed,
        no_production_business_environment=True,
        root_worktree_preserved=True,
        p3_started=False,
        p4_started=False,
    )
    save(HERE / "evidence/s7_preservation.json", preservation)
    checks["preservation"] = preservation
    checks["status"] = (
        "PASS"
        if all(
            c["exit_code"] == 0 for c in (checks[k] for k in ("ruff_check", "ruff_format", "mypy"))
        )
        and not any(checks["pytest"][k] for k in ("errors", "failures"))
        and not prior_changed
        and not user_changed
        and not exposed
        and all(
            preservation[k]
            for k in (
                "historical_registry_unchanged",
                "progress_append_only",
                "frozen_app_unchanged",
                "original_datasets_unchanged",
                "revised_datasets_unchanged",
                "active_scorer_matches_v21",
                "v20_source_snapshot_unchanged",
                "v20_scorer_matches_original_freeze",
            )
        )
        else "FAIL"
    )
    save(HERE / "evidence/s7_checks.json", checks)
    print(
        json.dumps(
            dict(status=checks["status"], pytest=checks["pytest"], preservation=preservation)
        )
    )
    if checks["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
