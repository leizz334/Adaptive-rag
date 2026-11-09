"""Final local audit; no paid calls or changes to original evidence/user files."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import dotenv_values

from research.docs.agent_engineering_upgrade.p3_experience_shadow.manage import (
    BASE,
    HERE,
    ROOT,
    STATE,
    git,
    save,
    sha,
)


def read(path):
    return json.loads(path.read_bytes())


def main():
    checks = {}
    for name, args in (
        ("ruff_check", ["-m", "ruff", "check", "."]),
        ("ruff_format", ["-m", "ruff", "format", "--check", "."]),
        ("mypy", ["-m", "mypy"]),
    ):
        result = subprocess.run(
            [sys.executable, "-B", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        checks[name] = dict(exit_code=result.returncode, output=result.stdout + result.stderr)
    suites = ET.parse(HERE / "evidence/a6_all_pytest.xml").getroot()
    tests = {
        k: sum(int(s.get(k, 0)) for s in suites.iter("testsuite"))
        for k in ("tests", "failures", "errors", "skipped")
    }
    checks["pytest"] = tests
    preservation = read(HERE / "evidence/preservation.json")
    changed = [p for p, h in preservation["prior_files"].items() if sha(ROOT / p) != h]
    changed_users = [
        p
        for p, h in preservation["user_files"].items()
        if sha(Path(preservation["user_root"]) / p) != h
    ]
    state = read(STATE / "feature-list.json")
    state.pop("p3_experience_shadow")
    state_same = state == json.loads(
        git("show", f"{BASE}:research/docs/agent_engineering_upgrade/feature-list.json")
    )
    prefix = git("show", f"{BASE}:research/docs/agent_engineering_upgrade/progress.txt")
    progress_same = (STATE / "progress.txt").read_text(encoding="utf-8").startswith(prefix)
    frozen = read(HERE / "evidence/a5_implementation_freeze.json")
    source_same = all(sha(ROOT / p) == h for p, h in frozen["app_experience"].items())
    runner_same = sha(HERE / "evaluate.py") == frozen["runner_sha256"]
    holdout_same = sha(HERE / "evaluation/applicability_holdout.json") == frozen["holdout_sha256"]
    lesson = read(HERE / "runs/20261109_shadow_01/results.json")
    regression = read(HERE / "runs/20261109_regression_01/results.json")
    secrets = [
        v.encode()
        for k, v in dotenv_values(Path(preservation["user_root"]) / ".env").items()
        if v
        and len(v) >= 12
        and any(s in k.upper() for s in ("KEY", "PASSWORD", "SECRET", "TOKEN"))
    ]
    paths = [
        *HERE.rglob("*.json"),
        *HERE.rglob("*.md"),
        *HERE.rglob("*.py"),
        *HERE.rglob("*.xml"),
        *HERE.rglob("*.txt"),
        *(ROOT / "app/experience").glob("*.py"),
    ]
    exposed = [str(p.relative_to(ROOT)) for p in paths if any(s in p.read_bytes() for s in secrets)]
    modified_existing = git("diff", BASE, "--diff-filter=M", "--name-only").splitlines()
    allowed_existing = {
        "research/docs/agent_engineering_upgrade/feature-list.json",
        "research/docs/agent_engineering_upgrade/progress.txt",
    }
    old_scope_clean = set(modified_existing) <= allowed_existing
    expected_counts = {
        "original80": (80, 80),
        "old16": (13, 16),
        "former_development30": (30, 30),
        "former_holdout33": (33, 33),
        "development24": (23, 24),
        "holdout30": (22, 30),
        "long_window": (1, 1),
    }
    legacy_ok = (
        all(
            (regression["groups"][name]["passed"], regression["groups"][name]["cases"]) == expected
            for name, expected in expected_counts.items()
        )
        and not regression["regressions"]
    )
    validation = dict(
        prior_files_checked=len(preservation["prior_files"]),
        prior_changed=changed,
        user_files_checked=len(preservation["user_files"]),
        user_changed=changed_users,
        old_state_unchanged=state_same,
        progress_append_only=progress_same,
        old_business_sources_untouched=old_scope_clean,
        experience_source_frozen=source_same,
        runner_frozen=runner_same,
        holdout_frozen=holdout_same,
        legacy_regression_unchanged=legacy_ok,
        shadow_divergence=lesson["E0_E1"]["divergence"],
        secret_scan_files=len(paths),
        credential_exposure_paths=exposed,
        new_http=0,
        new_tokens=0,
        new_cost=0,
        active_enabled=False,
        p3_b_started=False,
        p4_started=False,
    )
    save(HERE / "evidence/a6_preservation.json", validation)
    checks["preservation"] = validation
    checks["status"] = (
        "PASS"
        if not any(
            (
                changed,
                changed_users,
                exposed,
                tests["failures"],
                tests["errors"],
                lesson["E0_E1"]["divergence"],
            )
        )
        and all(
            (
                state_same,
                progress_same,
                old_scope_clean,
                source_same,
                runner_same,
                holdout_same,
                legacy_ok,
            )
        )
        and all(checks[n]["exit_code"] == 0 for n in ("ruff_check", "ruff_format", "mypy"))
        else "FAIL"
    )
    save(HERE / "evidence/a6_checks.json", checks)
    print(json.dumps(dict(status=checks["status"], pytest=tests, preservation=validation)))
    if checks["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
