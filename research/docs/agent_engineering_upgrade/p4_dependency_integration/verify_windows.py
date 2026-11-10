"""Read-only preservation/style evidence. No model/service/database operations."""

import json
import subprocess
import sys
from pathlib import Path

from .manage import BASE, HERE, REVIEW, ROOT, STATE, git, save, sha

ALLOWED = {
    "app/api/dependencies.py",
    "app/api/routes/admin.py",
    "app/api/routes/chat.py",
    "app/config/settings.py",
    "app/main.py",
    "alembic/env.py",
    "tests/e2e/test_chat_api.py",
    "research/docs/agent_engineering_upgrade/p4_api_e2e/runner.py",
    "research/docs/agent_engineering_upgrade/p4_api_e2e/worker.py",
    "research/docs/agent_engineering_upgrade/p2_quality/test_p2q_real.py",
}


def main():
    target = HERE / "evidence/windows_audit.json"
    if target.exists():
        raise FileExistsError("Preserve prior verification; choose a new evidence revision")
    inventory = json.loads((HERE / "evidence/preservation.json").read_bytes())
    changed = {p for p, digest in inventory["prior_files"].items() if sha(ROOT / p) != digest}
    assert changed == ALLOWED, sorted(changed ^ ALLOWED)
    assert sha(ROOT / REVIEW) == inventory["review_sha256"]
    assert all(
        sha(Path(inventory["user_root"]) / p) == digest
        for p, digest in inventory["root_user_files"].items()
    )
    baseline = json.loads(
        subprocess.check_output(
            ["git", "show", f"{BASE}:research/docs/agent_engineering_upgrade/feature-list.json"],
            cwd=ROOT,
        )
    )
    state = json.loads((STATE / "feature-list.json").read_bytes())
    phase = state.pop("p4_dependency_integration")
    assert state == baseline and phase["active_enabled"] is False
    old_progress = subprocess.check_output(
        ["git", "show", f"{BASE}:research/docs/agent_engineering_upgrade/progress.txt"], cwd=ROOT
    )
    assert (STATE / "progress.txt").read_bytes().startswith(old_progress)
    assert git("branch", "--show-current") == "codex/p4-dependency-integration"
    assert git("remote", "get-url", "origin") == "https://github.com/leizz334/Adaptive-rag.git"
    # Inspect current secrets in memory only; do not expose their values in evidence.
    secrets = []
    env = Path(inventory["user_root"]) / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                value = value.strip().strip("\"'")
                if (
                    any(
                        word in key.upper()
                        for word in ("API_KEY", "PASSWORD", "TOKEN", "AUTH_CREDENTIALS")
                    )
                    and len(value) >= 12
                ):
                    secrets.append(value.encode())
    # Include generated scratch credentials in the export check as well.
    for parent in (ROOT / "scratch", ROOT / ".scratch", HERE / ".private"):
        if parent.exists():
            for manifest in parent.rglob("manifest.json"):
                try:
                    obj = json.loads(manifest.read_bytes())
                    if obj.get("project", "").startswith("p4b_") and isinstance(
                        obj.get("password"), str
                    ):
                        secrets.append(obj["password"].encode())
                except (OSError, ValueError):
                    pass
    paths = set(git("diff", "--name-only", BASE).splitlines()) | set(
        git("ls-files", "--others", "--exclude-standard").splitlines()
    )
    exported = []
    for name in paths - {REVIEW}:
        path = ROOT / name
        if path.is_file():
            data = path.read_bytes()
            assert not any(value in data for value in secrets), "secret detected in export: " + name
            assert not any(part in {".private", ".env"} for part in path.relative_to(ROOT).parts)
            exported.append(name)
    save(
        target,
        dict(
            baseline=BASE,
            checked_prior_files=len(inventory["prior_files"]),
            authorized_prior_changes=sorted(changed),
            immutable_history_gold_preserved=True,
            user_files_preserved=len(inventory["root_user_files"]),
            edited_csv_preserved=True,
            secret_scan="PASS_VALUES_NOT_RECORDED",
            export_files_checked=len(exported),
            root_untouched=True,
            no_new_worktree=True,
        ),
    )
    outputs = []
    for args in (
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
    ):
        done = subprocess.run(
            [sys.executable, "-B", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
        )
        outputs.append(
            dict(
                command=["python", "-B", *args],
                exit_code=done.returncode,
                stdout=done.stdout,
                stderr=done.stderr,
            )
        )
    save(HERE / "evidence/windows_style_final.json", outputs)
    assert all(o["exit_code"] == 0 for o in outputs)
    print("Preservation, secret export scan, Ruff check/format and Mypy PASS")


if __name__ == "__main__":
    main()
