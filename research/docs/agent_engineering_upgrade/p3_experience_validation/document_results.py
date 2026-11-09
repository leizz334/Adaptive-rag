"""Render B0 evidence and audit preservation without rerunning any experiment."""

import csv
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
BASE = "04ccadb661bacfe4b09616ad11226288d4af8bf3"
RUN = HERE / "runs/20261109_B0_01"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def audit():
    inventory = read(HERE / "evidence/preservation.json")
    changed = [p for p, h in inventory["prior_files"].items() if sha(ROOT / p) != h]
    users = Path(inventory["user_root"])
    user_changes = [p for p, h in inventory["user_files"].items() if sha(users / p) != h]
    old = json.loads(
        git("show", f"{BASE}:research/docs/agent_engineering_upgrade/feature-list.json")
    )
    current = read(STATE / "feature-list.json")
    phase = current.pop("p3_experience_validation")
    assert current == old
    old_progress = git("show", f"{BASE}:research/docs/agent_engineering_upgrade/progress.txt")
    assert (STATE / "progress.txt").read_bytes().startswith(old_progress)
    assert not changed and not user_changes
    frozen = read(HERE / "evidence/b0_freeze.json")
    assert all(sha(ROOT / p) == h for p, h in frozen["sources"].items())
    assert all(sha(HERE / "datasets" / p) == h for p, h in frozen["datasets"].items())
    assert (
        sha(HERE.parent / "p3_experience_shadow/runs/20261109_shadow_01/experience_candidates.json")
        == frozen["candidate_export_sha256"]
    )
    rows = list(
        csv.DictReader((HERE / "human_review_template.csv").open(encoding="utf-8-sig", newline=""))
    )
    assert len(rows) == 7
    human = [
        "factual_correctness",
        "completeness",
        "faithfulness",
        "safety",
        "overall_verdict",
        "reviewer_name",
        "reviewed_at",
        "notes",
    ]
    assert all(not r[k] for r in rows for k in human)
    assert not phase["active_enabled"] and not phase["human_review_received"]
    paths = git("diff", "--name-only", BASE).decode().splitlines()
    allowed = {
        "app/experience/review_applicability.py",
        "tests/unit/test_experience_review_applicability.py",
        "tests/unit/test_experience_b0_review.py",
        "tests/unit/test_experience_matching_metrics.py",
        "research/docs/agent_engineering_upgrade/feature-list.json",
        "research/docs/agent_engineering_upgrade/progress.txt",
    }
    assert all(p in allowed or p.startswith(HERE.relative_to(ROOT).as_posix() + "/") for p in paths)
    # Read actual root credentials only into memory; report counts, never values.
    secrets = []
    for line in (users / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            value = value.strip().strip("\"'")
            if (
                any(t in key.upper() for t in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
                and len(value) >= 12
            ):
                secrets.append(value.encode())
    new_files = [ROOT / p for p in paths if (ROOT / p).is_file()]
    new_files += [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    assert not any(value in p.read_bytes() for value in secrets for p in new_files)
    result = dict(
        historical_files_checked=len(inventory["prior_files"]),
        historical_files_changed=changed,
        root_user_files_checked=len(inventory["user_files"]),
        root_user_files_changed=user_changes,
        historical_namespaces_unchanged=True,
        progress_prefix_preserved=True,
        source_data_and_candidate_freeze_preserved=True,
        human_rows=7,
        human_fields_filled=0,
        original_business_files_changed=0,
        phase_paths_only=True,
        actual_secret_matches=0,
        experience_active_enabled=False,
        B2_B3_started=False,
        new_model_http=0,
    )
    save(HERE / "evidence/preservation_verified.json", result)
    return result


def report():
    results = read(RUN / "results.json")
    lines = [
        "# P3-B0 Experience applicability",
        "",
        "B0 engineering and bounded relevance validation completed. Human approval and injection benefit remain unverified. All three original candidate records stay NEEDS_REVIEW / UNREVIEWED; none is promoted to VERIFIED_OFFLINE by this task.",
        "",
        "## Verified baseline and minimal change",
        "",
        f"Local/remote P3-A baseline {BASE} was verified before creating the isolated codex/p3-experience-validation worktree. Fresh baseline548tests passed. Pre-evaluation source/data checkpoint is a92164d. The original app/experience/applicability.py, catalog, candidate records and all business/Graph/M2/authorization code remain byte-identical.",
        "",
        "The original boolean conflates principle relevance with permission to use an experience. Its exclusions are appropriate as execution restrictions, but suppress useful review of how to handle risk. New review_applicability.py is a separate versioned advisory API. It returns MATCH_FOR_REVIEW, NO_MATCH or DEFER; every outcome forbids execution/injection/human approval and retains the original execution exclusions. It does not wire a new matcher into the Agent or implement B2 retrieval/injection.",
        "",
        "Identity/scope/version/expiry/rejection checks precede private reference resolution. Claimed tags must match hash-bound reviewed structural observations; provenance failure is DEFER. Known-empty evidence differs from unknown evidence. Risky relevant contexts carry explicit pending-write, untrusted-data, clarification, freshness, evidence-limit and Judge-category obligations. No permission, Owner, HITL or idempotency check is relaxed. A MATCH_FOR_REVIEW must never be interpreted as injection eligibility.",
        "",
        "## Eight frozen misses",
        "",
        "These are candidate/task judgments, not eight distinct user tasks. The original32case Gold and baseline TP12/FP0/FN8/TN76 are reproduced exactly. Root cause is demonstrated by the old matcher path and catalog exclusions, not inferred from final failure alone.",
        "",
        "| Frozen case | Candidate family | First excluding v1 condition | C1 disposition |",
        "| --- | --- | --- | --- |",
    ]
    for miss in read(RUN / "eight_misses.json")["cases"]:
        reason = ", ".join(miss["excluded_contexts"]) or "required evidence_available absent"
        lines.append(
            f"| {miss['case_id']} | {miss['family']} | {reason} | Review only; original restrictions retained |"
        )
    lines += [
        "",
        "Mixed2misses are untrusted text and ambiguity; Judge2misses are pending-write/untrusted contexts; Fallback4misses include pending writes, untrusted data and unavailable evidence. C1 attaches constraints instead of declaring a safe operation possible. Unknown evidence permits only limitation-oriented review, never invented facts.",
        "",
        "## Controlled comparison",
        "",
        "C0 is the unchanged v1 matcher; C1 is source-bound principle review. Same three candidates, task inputs, Gold, scope, fixed UTC clock and source versions. Predictions are computed before loading each cohort Gold. Original relevance labels are unchanged. Permission semantics are deliberately separated in C1; these results measure relevance, not equal production authorization policies.",
        "",
        "| Cohort | Arm | TP | FP | FN | TN | Precision | Recall |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cohort, data in results["cohorts"].items():
        for arm, m in data["arms"].items():
            lines.append(
                f"| {cohort} ({data['cases']} tasks ×3candidates) | {arm} | {m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | {m['precision']:.2%} | {m['recall']:.2%} |"
            )
    lines += [
        "",
        "| Candidate | Old cohort C0→C1 TP/FN | New blind C0→C1 TP/FN | C1 blind contract | Approval |",
        "| --- | --- | --- | --- | --- |",
    ]
    for family in results["cohorts"]["blind_holdout"]["families"]:
        old = results["cohorts"]["consumed_diagnostics"]["families"][family]
        blind = results["cohorts"]["blind_holdout"]["families"][family]
        lines.append(
            f"| {family} | {old['C0']['TP']}/{old['C0']['FN']}→{old['C1']['TP']}/{old['C1']['FN']} | {blind['C0']['TP']}/{blind['C0']['FN']}→{blind['C1']['TP']}/{blind['C1']['FN']} | PASS bounded relevance/guards | Pending human/B2 |"
        )
    lines += [
        "",
        "C1 safety conflicts and missing-required-guard decisions are0in all cohorts. C0 has no structured guard envelope, so this does not claim guard equivalence. Three development C0positive→C1negative transitions remove three false-positive labels; zero correct positive labels become negative. Old/blind negative matching transitions0. Agent negative transfer is NOT_RUN, not inferred from matcher scores.",
        "",
        "## Dataset and validation limits",
        "",
        "New development24and independent holdout32are frozen separately with Gold hashes in evidence/b0_freeze.json. The implementation was frozen before concrete holdout inputs/Gold/results were read. Independent AI authorship and pre-freeze code review were procedurally separated; filesystem access was not cryptographically blinded. The author saw the public catalog and some old candidate-filter code; the full disclosure is in datasets/blind_manifest.json. This is model-assisted synthetic Gold, not human labeling. These inputs are now consumed regression data; no post-holdout tuning was performed.",
        "",
        "Structural tags and source hashes do not prove natural-language feature extraction, production identity or experience utility. Neither production retrieval nor isolated injection is tested yet. All three relevance contracts pass this bounded test, but VERIFIED_EXPERIENCES=0, HUMAN_CALIBRATION=NOT_RUN, EXPERIENCE_BENEFIT=NOT_ESTABLISHED.",
        "",
        "RED/GREEN evidence:18initial failures, independent2restriction-retention failures and1fresh-read guard failure were corrected before freeze;24coretests pass. Original evidence remains. Fresh full regression initially577PASS/1FAIL in a mocked historical crash/replay test; its isolated diagnostic passes, and the full serial recheck578PASS/0FAIL/0ERROR/0SKIP. Its intermittent root cause is not established; the safety stop refused an uncertain simulated request. The initial failure is retained, not hidden or classified as a live-model failure. Ruff check/format pass; Mypy149source files pass. New model requests/tokens/cost0.",
        "",
        "Raw immutable run: runs/20261109_B0_01/{experiment_config,results,validation}.json plus per-cohort predictions/scores and eight_misses.json. Audit: evidence/preservation_verified.json. Next: deliver B1packet, ordinary push/ls-remote, then pause. B2/B3 require actual human review and explicit continuation. Production ACTIVE and P4 remain off.",
    ]
    (HERE / "P3-B0_APPLICABILITY_REPORT.md").write_bytes(("\n".join(lines) + "\n").encode())


def validation():
    evidence = {}
    for path in sorted((HERE / "evidence").glob("*pytest.xml")):
        suites = ET.parse(path).getroot().findall("testsuite")
        evidence[path.name] = {
            k: sum(int(s.get(k, 0)) for s in suites)
            for k in ("tests", "failures", "errors", "skipped")
        }
    save(HERE / "evidence/regression_summary.json", evidence)
    return evidence


if __name__ == "__main__":
    report()
    print(json.dumps(dict(preservation=audit(), pytest=validation())))
