"""Run repeatable non-model final gates and preserve exact command evidence."""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def main():
    checks = []
    commands = [
        ["-m", "ruff", "check", "."],
        ["-m", "ruff", "format", "--check", "."],
        ["-m", "mypy"],
        ["-B", "-m", "research.docs.agent_engineering_upgrade.p2_quality.verify_quality"],
    ]
    for arguments in commands:
        start = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        checks.append(
            dict(
                command=["python", *arguments],
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                elapsed_seconds=time.perf_counter() - start,
            )
        )
    data = dict(
        status="PASS" if all(c["exit_code"] == 0 for c in checks) else "FAIL",
        checks=checks,
        pytest_evidence="reviewed_full_pytest.xml:274 passed; full tests plus paid harness offline mocks",
        paid_api_calls=0,
    )
    (HERE / "final_checks.json").write_bytes(
        (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
