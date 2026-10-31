#!/usr/bin/env bash
# Repeatable recovery checks only. Does not initialize Git or mutate the project.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

STATE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(git -C "$STATE_DIR" rev-parse --show-toplevel)"
printf 'P0 recovery directory: %s\n' "$STATE_DIR"
git -C "$REPO_DIR" status --short
git -C "$REPO_DIR" log -4 --oneline

if command -v conda >/dev/null 2>&1; then
    CONDA_CMD="$(command -v conda)"
elif command -v conda.exe >/dev/null 2>&1; then
    CONDA_CMD="$(command -v conda.exe)"
elif [[ -n "${CONDA_EXE:-}" && -f "$CONDA_EXE" ]]; then
    CONDA_CMD="$CONDA_EXE"
else
    printf 'Conda unavailable. Open a shell with adaptive-rag available; do not install or activate another environment.\n' >&2
    exit 2
fi

"$CONDA_CMD" run --no-capture-output -n adaptive-rag python -B - "$STATE_DIR" <<'PY'
import json
import pathlib
import subprocess
import sys

state_dir = pathlib.Path(sys.argv[1]).resolve()
state = json.loads((state_dir / "feature-list.json").read_text(encoding="utf-8"))
assert (state_dir / "progress.txt").is_file(), "Missing progress.txt; reconcile, do not reinitialize"
assert state["phase"] in {"P0", "P1"}
tasks = state["tasks"]
assert [task["task_id"] for task in tasks[:7]] == ["P0-" + letter for letter in "ABCDEFG"]
if state["phase"] == "P1":
    assert [task["task_id"] for task in tasks[7:]] == ["P1-" + letter for letter in "ABCDEF"]
required = {
    "task_id", "description", "dependencies", "status", "passes",
    "acceptance_criteria", "evidence_files", "validation_results", "commit_hash", "next_action",
}
by_id = {task["task_id"]: task for task in tasks}
for task in tasks:
    assert required <= task.keys(), task["task_id"]
    assert isinstance(task["passes"], bool)
    assert all(dep in by_id for dep in task["dependencies"])
    if task["passes"]:
        assert task["status"] == "completed", task["task_id"]
        assert all((state_dir / path).is_file() for path in task["evidence_files"]), task["task_id"]
        assert task["validation_results"], task["task_id"]
    if task["commit_hash"]:
        subprocess.run(["git", "-C", str(state_dir), "cat-file", "-e", task["commit_hash"] + "^{commit}"], check=True)
next_task = next((task for task in tasks if not task["passes"] and all(by_id[dep]["passes"] for dep in task["dependencies"])), None)
print("Python:", sys.executable)
print("State JSON/schema/dependencies: PASS")
print("Completed:", ", ".join(task["task_id"] for task in tasks if task["passes"]) or "none")
print("Next dependency-ready task:", next_task["task_id"] if next_task else "none")
print("Recovery check only. No task was started by this script.")
PY
