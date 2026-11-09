"""Run local non-model gates and preserve command outputs for handoff."""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    checks = []
    for arguments in (
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
        [str(HERE / "prepare_human_review.py")],
    ):
        result = subprocess.run(
            [sys.executable, "-B", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        checks.append(
            dict(
                command=[sys.executable, "-B", *arguments],
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        )
        print(json.dumps(checks[-1], ensure_ascii=True))
    target = HERE / "evidence/b0_b1_checks.json"
    if target.exists():
        raise FileExistsError("Preserve earlier check evidence")
    target.write_bytes((json.dumps(checks, ensure_ascii=False, indent=2) + "\n").encode())
    assert all(c["exit_code"] == 0 for c in checks), "Retain failures before correction"


if __name__ == "__main__":
    main()
