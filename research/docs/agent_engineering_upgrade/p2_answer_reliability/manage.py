"""Append-only phase registration/checkpoints; never invokes Initializer."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = HERE.parent
BASE = "e74f01db65fb9f3df929cdf5932919e1f10e453e"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def checkpoint(
    task, evidence, validation, next_action, *, passes=True, status="completed", **details
):
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    phase = state["p2_answer_reliability"]
    head = git("rev-parse", "HEAD")
    for prior in phase["tasks"]:
        if prior["passes"] and not prior["commit_hash"] and prior["TASK_ID"] != task:
            prior["commit_hash"] = head
    current = next(t for t in phase["tasks"] if t["TASK_ID"] == task)
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


def register():
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    assert "p2_answer_reliability" not in state, "Already registered; resume checkpoints"
    criteria = [
        [
            "Verify actual pushed P2-R and source freeze",
            "Freeze previous evidence/Gold/config/Prompt/user files and reproduce344tests",
        ],
        [
            "RED/GREEN Judge schema/errors/finish_reason and grounded safe fallback",
            "No false model-state message, unrelated excerpt or unconfirmed write claim; SSE cleanup",
        ],
        [
            "Independent deterministic answer facts/completeness/evidence oracle",
            "Gold isolated from Agent; unknown semantics NOT_ASSESSED; invalid judge is not PASS",
        ],
        [
            "Diagnose known remaining capabilities; minimal general goal/evidence mapping",
            "Conjunction/negation/fresh business versus policy; preserve Owner/HITL/idempotency",
        ],
        [
            "Freeze >=20development and >=20holdout answer-annotated diverse Chinese tasks",
            "UTF8/Gold/state/data overlap gates and honest holdout isolation",
        ],
        [
            "Actual S0/S1/S2/S3 source controls, common M2/data/scorer/business fixtures",
            "All old datasets/longwindow/safety/new answer checks; preserve regressions and metric distinctions",
        ],
        [
            "New durable bounded350HTTP/300ktoken/estimated3USD ledger",
            "Source-paired real semantic facts/coverage or honest partial stop; uncertain requests never retried",
        ],
        [
            "Fullpytest/Ruff/Mypy, safety/SSE/eval/provider/tracing checks",
            "Historical and user preservation; task commits, authorized normalpush+lsremote, STOP",
        ],
    ]
    state["p2_answer_reliability"] = dict(
        phase="P2-S",
        status="in_progress",
        baseline_commit=BASE,
        tasks=[
            dict(
                TASK_ID=f"P2-S{i}",
                status="pending",
                passes=False,
                dependencies=[f"P2-S{i-1}"] if i else [],
                acceptance_criteria=c,
                evidence=[],
                validation=None,
                commit_hash=None,
                next_action="Follow P2-S_PLAN.md",
            )
            for i, c in enumerate(criteria)
        ],
        budget=dict(http=350, tokens=300000, estimated_usd=3, per_scenario_http=24, concurrency=1),
        p3_started=False,
        p4_started=False,
    )
    save(path, state)
    with (STATE / "progress.txt").open("ab") as f:
        f.write(
            f"\nP2_S_AUTHORIZED\nBASELINE={BASE};remoteverified;WORKTREE={ROOT};rootuserworkpreserved\nNEXT_ACTION=S0baseline;doNotTouchOldPendingRequests\n".encode()
        )
    prior = git(
        "ls-tree", "-r", "--name-only", BASE, "research/docs/agent_engineering_upgrade"
    ).splitlines()
    users = Path("D:/Code/Adaptive-rag")
    userpaths = (
        git("diff", "--name-only", root=users).splitlines()
        + git("ls-files", "--others", "--exclude-standard", root=users).splitlines()
        + [".env"]
    )

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    frozen = {
        p: sha(ROOT / p) for p in prior if not p.endswith(("feature-list.json", "progress.txt"))
    }
    save(
        HERE / "evidence/preservation.json",
        dict(
            baseline=BASE,
            prior_artifacts=frozen,
            user_root=str(users),
            user_files={p: sha(users / p) for p in sorted(set(userpaths)) if (users / p).is_file()},
            source_files={
                p: sha(ROOT / p)
                for p in git("ls-tree", "-r", "--name-only", BASE, "app", "eval").splitlines()
            },
        ),
    )


if __name__ == "__main__":
    register()
