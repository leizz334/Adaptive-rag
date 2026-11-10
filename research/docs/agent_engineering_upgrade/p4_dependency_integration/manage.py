"""P4-B task registry append/checkpoints; never reinitialize existing project."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
BASE = "7ee14234299b640e733c7099816f3a7ed7e4dc0a"
REVIEW = (
    "research/docs/agent_engineering_upgrade/p3_experience_validation/human_review_template.csv"
)


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def append(text):
    with (STATE / "progress.txt").open("ab") as stream:
        stream.write(("\n" + text + "\n").encode())


def register():
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    assert "p4_dependency_integration" not in state, "Resume; do not repeat registration"
    assert (
        git("rev-parse", "HEAD") == BASE
        and git("branch", "--show-current") == "codex/p4-dependency-integration"
    )
    assert git("ls-remote", "--heads", "origin", "refs/heads/codex/p4-api-e2e").split()[0] == BASE
    assert sha(ROOT / REVIEW) == "9ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7"
    prior = (
        subprocess.check_output(["git", "ls-tree", "-rz", "--name-only", BASE], cwd=ROOT)
        .decode()
        .split("\0")
    )
    users = json.loads((STATE / "p4_api_e2e/evidence/preservation.json").read_bytes())
    excluded = {
        REVIEW,
        "research/docs/agent_engineering_upgrade/feature-list.json",
        "research/docs/agent_engineering_upgrade/progress.txt",
    }
    save(
        HERE / "evidence/preservation.json",
        dict(
            baseline=BASE,
            new_worktree_created=False,
            prior_files={p: sha(ROOT / p) for p in prior if p and p not in excluded},
            review_sha256=sha(ROOT / REVIEW),
            user_root=users["user_root"],
            root_user_files={
                p: sha(Path(users["user_root"]) / p) for p in users["root_user_files"]
            },
        ),
    )
    criteria = [
        [
            "Server verified credential/subject/role/expiry, no client-ID trust",
            "Required-auth real HTTPforgery/Owner/Session/SSE/admin verification; explicit test-only compatibility",
            "RED/GREEN/security review/checkpoint",
        ],
        [
            "Isolated real-service config and guarded PostgreSQL/Redis/Qdrant/API tests prepared",
            "Windowschecks PASS; real service results BLOCKED/NOT_RUN, not mock replacements",
            "Ubuntu runbook/recovery, ordinarypush+lsremote andPAUSE",
        ],
        [
            "Ubuntu restore verifiedHEAD and owned isolated Docker services",
            "Real PG/Redis/Qdrantpersistence/transactions/TTL/filter/error/recovery tests",
        ],
        [
            "Real dependency HTTP/SSE/auth/HITL/concurrency/failure tests and minimum fixes",
            "Full regression/evidence/commits/push andSTOP; no laterphase",
        ],
    ]
    state["p4_dependency_integration"] = dict(
        phase="P4-B",
        status="WINDOWS_B0_B1_IN_PROGRESS",
        baseline_commit=BASE,
        authorized_now=["P4-B0", "P4-B1"],
        environment="Windows",
        active_enabled=False,
        paid_model_calls_allowed=False,
        P4_C_started=False,
        tasks=[
            dict(
                TASK_ID=f"P4-B{i}",
                status="pending" if i < 2 else "waiting_ubuntu",
                passes=False,
                dependencies=[] if i == 0 else [f"P4-B{i-1}"],
                acceptance_criteria=c,
                evidence=[],
                validation=None,
                commit_hash=None,
                next_action="PLAN.md; pause afterB1forUbuntu",
            )
            for i, c in enumerate(criteria)
        ],
    )
    save(path, state)
    append(
        f"P4-B_WINDOWS_AUTHORIZED;BASE={BASE};fixed_worktree={ROOT};noInitializer/newworktree/paid/Active;nextB0/B1thenpushPAUSE_UBUNTU"
    )


def checkpoint(
    task, evidence, validation, next_action, *, passes=True, status="completed", **fields
):
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    tasks = state["p4_dependency_integration"]["tasks"]
    for old in tasks:
        if old["passes"] and not old["commit_hash"] and old["TASK_ID"] != task:
            old["commit_hash"] = git("rev-parse", "HEAD")
    selected = next(t for t in tasks if t["TASK_ID"] == task)
    selected.update(
        status=status,
        passes=passes,
        evidence=evidence,
        validation=validation,
        next_action=next_action,
        **fields,
    )
    save(path, state)
    append(
        f"{task}={status};passes={passes};previous_checkpoint={git('rev-parse','HEAD')}\nEVIDENCE={';'.join(evidence)}\nVALIDATION={validation}\nNEXT_ACTION={next_action}"
    )


if __name__ == "__main__":
    register()
