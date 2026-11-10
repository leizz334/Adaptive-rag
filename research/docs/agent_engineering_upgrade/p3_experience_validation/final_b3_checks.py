"""Final offline gates, preservation and presence-aware comparison evidence."""

import csv
import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from research.docs.agent_engineering_upgrade.p3_experience_validation.analyze_run import (
    compare_behavior,
)
from research.docs.agent_engineering_upgrade.p3_experience_validation.human_import import (
    validate_rows,
)
from research.docs.agent_engineering_upgrade.p3_experience_validation.manage import (
    HERE,
    ROOT,
    STATE,
    git,
    save,
    sha,
)
from research.docs.agent_engineering_upgrade.p3_experience_validation.prepare_human_review import (
    build_outputs,
)

BASE = "aae3f996c1e8f15aebe3391b6b22e6441862c768"


def read(path):
    return json.loads(path.read_bytes())


def source_blob(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def check_commands():
    target = HERE / "evidence/b3_checks.json"
    assert not target.exists(), "Preserve previous validation evidence"
    outputs = []
    for command in (
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
    ):
        result = subprocess.run(
            [sys.executable, "-B", *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            check=False,
        )
        outputs.append(
            dict(
                command=[sys.executable, "-B", *command],
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
    save(target, outputs)
    assert all(row["exit_code"] == 0 for row in outputs)


def audit():
    preservation = read(HERE / "evidence/preservation.json")
    assert all(sha(ROOT / p) == h for p, h in preservation["prior_files"].items())
    user_root = Path(preservation["user_root"])
    assert all(sha(user_root / p) == h for p, h in preservation["user_files"].items())
    frozen = read(HERE / "evidence/b2_freeze_v2.json")
    assert all(sha(ROOT / p) == h for p, h in frozen["files"].items())
    report = read(HERE / "human_review/20261110_submission_01/import_report.json")
    original = HERE / "human_review_template.csv"
    assert (
        sha(original)
        == report["input_sha256"]
        == sha(HERE / "human_review/20261110_submission_01/submitted_review.csv")
    )
    imported = validate_rows(
        list(csv.DictReader(io.StringIO(original.read_bytes().decode("utf-8-sig"), newline=""))),
        attested_by_user=True,
    )
    assert imported["overall_counts"] == report["overall_counts"]
    # Historical blank handoff is validated against Git, never restored over user edits.
    for name, data in build_outputs().items():
        relative = (HERE / name).relative_to(ROOT).as_posix()
        assert data == source_blob(relative)
    old_state = json.loads(source_blob("research/docs/agent_engineering_upgrade/feature-list.json"))
    current = read(STATE / "feature-list.json")
    old_phase, phase = (
        old_state.pop("p3_experience_validation"),
        current.pop("p3_experience_validation"),
    )
    assert old_state == current and old_phase["tasks"][:2] == phase["tasks"][:2]
    assert (
        (STATE / "progress.txt")
        .read_bytes()
        .startswith(source_blob("research/docs/agent_engineering_upgrade/progress.txt"))
    )
    assert not git("diff", "--name-only", BASE, "--", "app", "eval")
    baseline_paths = (
        subprocess.check_output(["git", "ls-tree", "-rz", "--name-only", BASE], cwd=ROOT)
        .decode()
        .split("\0")
    )
    modified = git("diff", "--name-only", BASE).splitlines()
    allowed_prior = {
        "research/docs/agent_engineering_upgrade/feature-list.json",
        "research/docs/agent_engineering_upgrade/progress.txt",
        (HERE / "RECOVERY.md").relative_to(ROOT).as_posix(),
        original.relative_to(ROOT).as_posix(),
        (HERE / ".gitattributes").relative_to(ROOT).as_posix(),
    }
    assert all(p not in baseline_paths or p in allowed_prior for p in modified)
    # Actual credentials never leave memory; no secret text appears in output.
    secrets = []
    for line in (user_root / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            value = value.strip().strip("\"'")
            if len(value) >= 12 and any(
                t in key.upper() for t in ("KEY", "TOKEN", "SECRET", "PASSWORD")
            ):
                secrets.append(value.encode())
    paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    assert not any(secret in p.read_bytes() for secret in secrets for p in paths)
    run = HERE / "runs/20261110_B2_02"
    results = read(run / "results.json")
    comparisons = []
    for row in results["rows"]:
        arms = {a: read(run / f"{row['case_id']}_{a}.json") for a in ("E0", "E1", "E2")}
        for arm in ("E1", "E2"):
            compared = compare_behavior(arms["E0"]["canonical"], arms[arm]["canonical"])
            assert compared["raw_equal"] == (arms["E0"]["canonical"] == arms[arm]["canonical"])
            comparisons.append(dict(case_id=row["case_id"], pair=f"E0/{arm}", **compared))
    assert all(row["decision_equal"] for row in comparisons)
    suite = ET.parse(HERE / "evidence/b3_final_pytest.xml").getroot().find("testsuite")
    assert suite.attrib["tests"] == "612" and all(
        suite.attrib[k] == "0" for k in ("failures", "errors", "skipped")
    )
    legacy = read(HERE / "runs/20261110_B3_legacy_01/results.json")
    assert not legacy["regressions"]
    result = dict(
        historical_files_preserved=len(preservation["prior_files"]),
        original_user_files_preserved=len(preservation["user_files"]),
        original_edited_review_preserved=True,
        original_edited_review_committed=False,
        frozen_B0_B1_Git_handoff_preserved=True,
        historical_namespaces_unchanged=True,
        B0_B1_tasks_unchanged=True,
        progress_prefix_preserved=True,
        existing_app_eval_changes=0,
        source_data_submission_freeze_preserved=True,
        actual_credential_matches=0,
        pytest=dict(tests=612, failures=0, errors=0, skipped=0),
        comparisons=comparisons,
        presence_aware_pair_count=len(comparisons),
        raw_changed_pairs=sum(not r["raw_equal"] for r in comparisons),
        decision_changed_pairs=sum(not r["decision_equal"] for r in comparisons),
        legacy_regressions=[],
        phase_quality="PARTIAL_PASS",
        experience_benefit="NOT_ESTABLISHED",
        active_enabled=False,
        p4_started=False,
        new_model_http=0,
        new_tokens=0,
        estimated_new_cost_usd=0,
    )
    save(HERE / "evidence/b3_preservation_and_comparison.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "comparisons"}))


if __name__ == "__main__":
    check_commands()
    audit()
