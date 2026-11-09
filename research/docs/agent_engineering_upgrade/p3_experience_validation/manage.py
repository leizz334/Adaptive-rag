"""Append P3-B state; B2/B3 remain gated by actual human review and continuation."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STATE = HERE.parent
BASE = "04ccadb661bacfe4b09616ad11226288d4af8bf3"


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
    assert "p3_experience_validation" not in state, "Resume phase; never reinitialize"
    criteria = [
        [
            "Diagnose8frozen false negatives without changing old Gold",
            "RED/GREEN minimal guarded applicability fix; new development and independently frozen blind data",
            "C0/C1 precision/recall/FP/FN and per-candidate safety outcomes; no unsafe authorization",
        ],
        [
            "Exactly7saved R1real public answers with query,actual evidence,AI controversies and blank human choices",
            "Index/packet/BOM CSV, hashes and absolute plus repository-relative paths; no human result fabricated",
            "Checkpoint/push and pause beforeB2 until completed human review plus continuation",
        ],
        [
            "Import and verify actual human review received afterB1 checkpoint",
            "Qualified experience only: isolated E0/E1/E2retrieval/injection benefit and independent negative-transfer checks; activeoff",
        ],
        [
            "AfterB2 run full engineering/security regressions and preserve failures",
            "Produce P4_E2E_TEST_PLAN.md but do not execute P4; final safe delivery",
        ],
    ]
    state["p3_experience_validation"] = dict(
        phase="P3-B",
        status="in_progress_before_human_review",
        baseline_commit=BASE,
        authorized_now=["P3-B0", "P3-B1"],
        human_review_received=False,
        human_review_validated=False,
        continue_instruction_received=False,
        active_enabled=False,
        p4_started=False,
        tasks=[
            dict(
                TASK_ID=f"P3-B{i}",
                status="pending" if i < 2 else "waiting_human_review",
                passes=False,
                dependencies=[f"P3-B{i-1}"] if i else [],
                acceptance_criteria=c,
                evidence=[],
                validation=None,
                commit_hash=None,
                next_action="P3-B_PLAN.md;stop after B1 for human review",
            )
            for i, c in enumerate(criteria)
        ],
    )
    save(path, state)
    finish_registration()


def finish_registration():
    """Recover the append-only registration if inventory enumeration was interrupted."""
    assert "p3_experience_validation" in json.loads((STATE / "feature-list.json").read_bytes())
    assert not (HERE / "evidence/preservation.json").exists(), "Preserve the completed inventory"
    prior = (
        subprocess.check_output(["git", "ls-tree", "-rz", "--name-only", BASE], cwd=ROOT)
        .decode("utf-8")
        .split(chr(0))
    )
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
                for p in prior
                if p
                and p
                not in {
                    "research/docs/agent_engineering_upgrade/feature-list.json",
                    "research/docs/agent_engineering_upgrade/progress.txt",
                }
            },
            user_root=str(users),
            user_files={p: sha(users / p) for p in sorted(set(userpaths)) if (users / p).is_file()},
        ),
    )
    with (STATE / "progress.txt").open("ab") as f:
        f.write(
            f"\nP3_B_AUTHORIZED_B0_B1\nBASELINE={BASE};remoteverified;WORKTREE={ROOT};B2B3_WAIT_HUMAN_AND_CONTINUE\nNEXT_ACTION=B0diagnose/fix/test;B1packet;pushandpause;noAPI/ACTIVE/P4\n".encode()
        )


def checkpoint(
    task, evidence, validation, next_action, *, passes=True, status="completed", **details
):
    path = STATE / "feature-list.json"
    state = json.loads(path.read_bytes())
    tasks = state["p3_experience_validation"]["tasks"]
    head = git("rev-parse", "HEAD")
    for old in tasks:
        if old["passes"] and not old["commit_hash"] and old["TASK_ID"] != task:
            old["commit_hash"] = head
    selected = next(t for t in tasks if t["TASK_ID"] == task)
    selected.update(
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
