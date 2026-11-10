"""P4-A Coding Agent checkpoints in the existing task registry; never initialize."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
BASE = "586d0e01381d69bdc1653e5563e3ce48e9b82219"
REVIEW = (
    "research/docs/agent_engineering_upgrade/p3_experience_validation/human_review_template.csv"
)


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())


def register():
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    assert "p4_api_e2e" not in state, "Resume; never repeat phase registration"
    assert (
        git("branch", "--show-current") == "codex/p4-api-e2e" and git("rev-parse", "HEAD") == BASE
    )
    assert (
        git("ls-remote", "--heads", "origin", "refs/heads/codex/p3-experience-validation").split()[
            0
        ]
        == BASE
    )
    assert sha(ROOT / REVIEW) == "9ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7"
    prior = (
        subprocess.check_output(["git", "ls-tree", "-rz", "--name-only", BASE], cwd=ROOT)
        .decode()
        .split("\0")
    )
    excluded = {
        REVIEW,
        "research/docs/agent_engineering_upgrade/feature-list.json",
        "research/docs/agent_engineering_upgrade/progress.txt",
    }
    original = STATE / "p3_experience_validation/evidence/preservation.json"
    users = json.loads(original.read_bytes())
    save(
        HERE / "evidence/preservation.json",
        dict(
            baseline=BASE,
            worktree=str(ROOT),
            new_worktree_created=False,
            prior_files={p: sha(ROOT / p) for p in prior if p and p not in excluded},
            edited_review_sha256=sha(ROOT / REVIEW),
            user_root=users["user_root"],
            root_user_files={p: sha(Path(users["user_root"]) / p) for p in users["user_files"]},
        ),
    )
    state["p4_api_e2e"] = dict(
        phase="P4-A",
        status="in_progress",
        baseline_commit=BASE,
        active_enabled=False,
        paid_calls_allowed=False,
        P4_B_started=False,
        tasks=[
            dict(
                TASK_ID=f"P4-A{i}",
                status="pending",
                passes=False,
                dependencies=[] if i == 0 else [f"P4-A{i-1}"],
                acceptance_criteria=criteria,
                evidence=[],
                validation=None,
                commit_hash=None,
                next_action="P4-A_PLAN.md",
            )
            for i, criteria in enumerate(
                [
                    [
                        "Verified existing worktree/CSV/baseline and isolated real Uvicorn/TCP startup",
                        "Concrete provider/DB/retrieval manifest and no outbound billing",
                    ],
                    [
                        "Real HTTP/SSE matrix checks response/answer/tools/state/trace",
                        "Preserve failures and distinguish missing trusted authentication as BLOCKED",
                    ],
                    [
                        "RED/GREEN minimal evidenced fixes and real HTTP regression",
                        "Full pytest/Ruff/Mypy and safety/preservation checks",
                        "Independent review/report/ordinary push+lsremote; no later P4phase",
                    ],
                ]
            )
        ],
    )
    save(path, state)
    append(
        f"P4-A_AUTHORIZED;BASE={BASE};fixed_existing_worktree={ROOT};review_preserved;next=A0realstartup;noinitializer/newworktree/paid/Active/P4B"
    )


def append(text):
    with (STATE / "progress.txt").open("ab") as stream:
        stream.write(("\n" + text + "\n").encode())


def checkpoint(
    task, evidence, validation, next_action, *, passes=True, status="completed", **fields
):
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    tasks = state["p4_api_e2e"]["tasks"]
    for prior in tasks:
        if prior["passes"] and not prior["commit_hash"] and prior["TASK_ID"] != task:
            prior["commit_hash"] = git("rev-parse", "HEAD")
    selected = next(row for row in tasks if row["TASK_ID"] == task)
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
