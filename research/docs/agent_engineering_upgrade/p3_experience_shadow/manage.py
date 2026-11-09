"""Append the authorized P3-A phase; never reruns project initialization."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
BASE = "70d65e36687ae31133b08aec065f0a3ca4a6b848"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def register():
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    assert "p3_experience_shadow" not in state, "Resume existing phase; do not register twice"
    criteria = [
        [
            "Verify local/remote P2-S HEAD, prior raw metrics and475fresh tests",
            "Preserve user files/history, freeze sources/Gold/logs, isolated branch",
        ],
        [
            "Review14saved real answers with claim-level evidence and separate dimensions",
            "Independent model review/disagreements/human packet; no invented human labels or paid replay",
        ],
        [
            "Evidence-backed failure taxonomy and bounded confidence; unknown versus evaluation artifact",
            "RED/GREEN classifier and provenance tests; no root inferred solely from score",
        ],
        [
            "Offline completed-trace shadow pipeline defaultoff; active rejected; no production injection",
            "Evidence-gated safe generic lessons, bounded duplication and failure isolation; RED/GREEN",
        ],
        [
            "Scoped relational persistence, lifecycle/version/review split, expiry/deletion/dedup",
            "SQLite persistence/rollback plus PostgreSQL DDL compatibility; isolation/PII/injection tests",
        ],
        [
            "E0/E1 same replay outputs/tools/DB; E2 independent applicability/safety controls",
            "Honest classification/validity/match metrics with no self-approved learned benefit",
        ],
        [
            "Fullpytest/Ruff/Mypy and historical security/provider/eval/trace regressions",
            "Preserve all history/user bytes; bounded model accounting; safe normalpush+lsremote andSTOP",
        ],
    ]
    state["p3_experience_shadow"] = dict(
        phase="P3-A",
        status="in_progress",
        baseline_commit=BASE,
        tasks=[
            dict(
                TASK_ID=f"P3-A{i}",
                status="pending",
                passes=False,
                dependencies=[f"P3-A{i-1}"] if i else [],
                acceptance_criteria=c,
                evidence=[],
                validation=None,
                commit_hash=None,
                next_action="P3-A_PLAN.md",
            )
            for i, c in enumerate(criteria)
        ],
        budget=dict(http_requests=120, tokens=120000, estimated_usd=2, concurrency=1),
        experience_mode="off",
        active_enabled=False,
        p3_b_started=False,
        p4_started=False,
    )
    save(path, state)
    baseline_paths = git(
        "ls-tree",
        "-r",
        "--name-only",
        BASE,
        "research/docs/agent_engineering_upgrade",
        "app",
        "eval",
        "knowledge",
    ).splitlines()
    users = Path("D:/Code/Adaptive-rag")
    userpaths = (
        git("diff", "--name-only", root=users).splitlines()
        + git("ls-files", "--others", "--exclude-standard", root=users).splitlines()
        + [".env"]
    )
    save(
        HERE / "evidence/preservation.json",
        dict(
            baseline=BASE,
            prior_files={
                p: sha(ROOT / p)
                for p in baseline_paths
                if not p.endswith(("feature-list.json", "progress.txt"))
            },
            user_root=str(users),
            user_files={p: sha(users / p) for p in sorted(set(userpaths)) if (users / p).is_file()},
        ),
    )
    with (STATE / "progress.txt").open("ab") as f:
        f.write(
            f"\nP3_A_AUTHORIZED\nBASELINE={BASE};remoteverified;WORKTREE={ROOT};userworkpreserved\nNEXT_ACTION=A0baseline;neverrepeatpaidP2Srequests;noACTIVE/P3B/P4\n".encode()
        )


def checkpoint(
    task, evidence, validation, next_action, *, passes=True, status="completed", **details
):
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    head = git("rev-parse", "HEAD")
    tasks = state["p3_experience_shadow"]["tasks"]
    for prior in tasks:
        if prior["TASK_ID"] != task and prior["passes"] and not prior["commit_hash"]:
            prior["commit_hash"] = head
    current = next(t for t in tasks if t["TASK_ID"] == task)
    current.update(
        status=status,
        passes=passes,
        evidence=evidence,
        validation=validation,
        next_action=next_action,
        **details,
    )
    save(path, state)
    with (STATE / "progress.txt").open("ab") as f:
        f.write(
            f"\n{task}={status};passes={passes};previous_checkpoint={head}\nEVIDENCE={';'.join(evidence)}\nVALIDATION={validation}\nNEXT_ACTION={next_action}\n".encode()
        )


if __name__ == "__main__":
    register()
