"""Read-only P2-R preservation, source, journal and delivery-readiness checks."""

import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = "09819352cc6df98b9f8cb42ffb56e9c8365b5793"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)

    preservation = read(HERE / "evidence/preservation.json")
    user_root = Path(preservation["user_root"])
    check(
        "prior_evidence_exact_worktree",
        all(digest(ROOT / p) == h for p, h in preservation["prior_artifacts"].items()),
    )
    check(
        "prior_evidence_exact_user_root",
        all(digest(user_root / p) == h for p, h in preservation["root_prior_artifacts"].items()),
    )
    check(
        "all_user_files_and_env_exact",
        all(digest(user_root / p) == h for p, h in preservation["user_files"].items()),
    )
    state_rel = "research/docs/agent_engineering_upgrade/feature-list.json"
    state = read(ROOT / state_rel)
    state.pop("p2_agent_quality")
    check("old_registry_unchanged", state == json.loads(git("show", f"{BASE}:{state_rel}")))
    progress = "research/docs/agent_engineering_upgrade/progress.txt"
    check(
        "old_progress_preserved",
        (ROOT / progress)
        .read_bytes()
        .replace(b"\r\n", b"\n")
        .startswith(git("show", f"{BASE}:{progress}").replace(b"\r\n", b"\n")),
    )
    freeze = read(HERE / "evidence/candidate_freeze.json")
    for label, snapshot in freeze["source_snapshots"].items():
        check(
            f"frozen_{label}_app",
            all(digest(Path(snapshot["root"]) / p) == h for p, h in snapshot["app_hashes"].items()),
        )
    check(
        "blind_dataset_frozen",
        digest(HERE / "datasets/blind_holdout.json") == freeze["blind_sha256"],
    )
    check(
        "dev_dataset_frozen",
        digest(HERE / "datasets/development.json") == freeze["development_sha256"],
    )
    changed = git("diff", "--name-only", BASE, "--", "app").decode().splitlines()
    expected = {
        "app/memory/context.py",
        "app/services/chat_service.py",
        "app/agents/nodes/planner.py",
        "app/agents/nodes/executor.py",
        "app/prompts/planner.py",
    }
    check("exact_five_production_files", set(changed) == expected)
    check("all_eval_gold_contracts_unchanged", not git("diff", BASE, "--", "eval").strip())
    # Early task scripts were formatted during final lint, with no semantic change.
    formatting = {}
    for name in (
        "analyze_baseline",
        "build_development",
        "dataset_gate",
        "diagnose",
        "manage",
        "real_report",
        "observation_scoring",
        "run_real",
    ):
        path = HERE / f"{name}.py"
        prior = git("show", f"HEAD:{path.relative_to(ROOT).as_posix()}").decode("utf-8")
        old_tree, new_tree = ast.parse(prior), ast.parse(path.read_bytes())
        unused = {"analyze_baseline": "Counter", "dataset_gate": "hashlib"}.get(name)
        if unused:
            check(
                f"{name}_removed_import_truly_unused",
                not any(isinstance(n, ast.Name) and n.id == unused for n in ast.walk(old_tree)),
            )
            old_tree.body = [
                n
                for n in old_tree.body
                if not (
                    isinstance(n, ast.Import | ast.ImportFrom)
                    and len(n.names) == 1
                    and n.names[0].name == unused
                )
            ]
        formatting[name] = ast.dump(old_tree) == ast.dump(new_tree)
    check("report_tools_only_format_and_verified_unused_import_cleanup", all(formatting.values()))
    live = HERE / "runs/20261105_R5_pairs_01"
    config = read(live / "experiment_config.json")
    check("paid_harness_frozen", digest(HERE / "real_pairs.py") == config["harness_sha256"])
    rows = read(live / "requests.json")
    check("unique_requests", len({(r["group"], r["sequence"]) for r in rows}) == len(rows) == 109)
    complete = [r for r in rows if r["status"] == "RESPONSE"]
    pending = [r for r in rows if r["status"] != "RESPONSE"]
    check(
        "108_responses_one_uncertain",
        len(complete) == 108
        and len(pending) == 1
        and pending[0]["transport_error_type"] == "ConnectError",
    )
    check("all_responses_http_200", all(r["http_status"] == 200 for r in complete))
    reported = sum((r.get("usage") or {}).get("total_tokens", 0) for r in complete)
    accounted = reported + sum(r["reserve_input"] + r["reserve_output"] for r in pending)
    check("reported_accounted_tokens", reported == 88858 and accounted == 92839)
    check("within_http_token_limits", len(rows) <= 420 and accounted <= 420000)
    analysis = read(live / "analysis.json")
    check("cost_estimate_within_limit", analysis["totals"]["estimated_usd"] <= 3)
    check(
        "partial_stopped_no_retry",
        read(live / "results.json")["status"] == "PARTIAL_UNCERTAIN_TRANSPORT_STOP",
    )
    for label in ("R0", "R1"):
        replay = read(HERE / f"evidence/r5_replay_{label}_v2/results.json")
        check(
            f"{label}_exact_local_replay",
            replay["complete"] == 8
            and replay["unknown"] == 0
            and replay["new_paid_api_calls"] == 0
            and all(g["oracle_equivalent"] for g in replay["groups"]),
        )
        check(
            f"{label}_live_journal_unchanged",
            all(digest(live / p) == h for p, h in replay["live_artifact_hashes"].items()),
        )
    # Never emit the actual secret or any matching context.
    from dotenv import dotenv_values

    key = dotenv_values(user_root / ".env").get("DEEPSEEK_API_KEY")
    check("key_loaded_for_local_audit_only", bool(key))
    tracked = (
        git("ls-files", "research/docs/agent_engineering_upgrade/p2_agent_quality")
        .decode()
        .splitlines()
    )
    check(
        "no_secret_in_phase_artifacts",
        all(key.encode() not in (ROOT / p).read_bytes() for p in tracked if (ROOT / p).is_file()),
    )
    check(
        "runtime_lock_untracked",
        not git(
            "ls-files",
            "research/docs/agent_engineering_upgrade/p2_agent_quality/runs/20261105_R5_pairs_01/.lock",
        ).strip(),
    )
    tree = ET.parse(HERE / "evidence/r6_all_pytest.xml")
    suites = list(tree.iter("testsuite"))
    tests = sum(int(t.attrib.get("tests", 0)) for t in suites)
    check(
        "full_pytest_green",
        tests >= 340
        and all(
            int(t.attrib.get("failures", 0)) + int(t.attrib.get("errors", 0)) == 0 for t in suites
        ),
    )
    p1 = read(HERE / "evidence/r6_p1_compatibility.json")
    check("p1_contract_compatibility_expected13of14", p1["cases"] == 14 and p1["passed"] == 13)
    result = dict(
        status="PASS",
        checks=checks,
        pytest=tests,
        original_evidence_files=len(preservation["prior_artifacts"]),
        preserved_user_files=len(preservation["user_files"]),
        candidate_source=freeze["candidate_commit"],
        http_attempts=len(rows),
        reported_tokens=reported,
        accounted_tokens=accounted,
        new_paid_calls=0,
        push_status="PENDING_DELIVERY_SEPARATE_EVIDENCE",
        phase_quality="PARTIAL_PASS",
    )
    (HERE / "evidence/r6_preservation_validation.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
