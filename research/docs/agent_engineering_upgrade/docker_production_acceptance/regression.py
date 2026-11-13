"""Reuse stopped, owned P4B dependencies; immutable fresh run IDs, no paid calls."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
STATE = ROOT / "research/docs/agent_engineering_upgrade"
PRIVATE = Path("/root/.local/state/adaptive-rag-production-20261113")
MANIFEST = STATE / "p4_dependency_integration/.private/p4b_ww_w4_20261113_01/manifest.json"
PYTHON = "/home/panda/.venvs/adaptive-rag-workbench/bin/python"
PREFIX = "research.docs.agent_engineering_upgrade."
action = sys.argv[1]
run_id = "prod_20261114_" + ("deps01" if action == "dependency" else "suite01")
os.environ.update(
    P4B_RUN_LIVE="1",
    P4B_MANIFEST=str(MANIFEST),
    P4_E2E_RUN_ID=run_id + "_http",
    P4B_AUTH_RUN_ID=run_id + "_auth",
    P4B_API_RUN_ID=run_id + "_api",
    DEEPSEEK_API_KEY="",
    EMBEDDING_API_KEY="",
    EXPERIENCE_MEMORY_MODE="off",
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    PYTHONUTF8="1",
    GIT_DIR="/mnt/d/Code/Adaptive-rag/.git/worktrees/p3-experience-validation",
    GIT_COMMON_DIR="/mnt/d/Code/Adaptive-rag/.git",
    GIT_WORK_TREE=str(ROOT),
    GIT_OBJECT_DIRECTORY="/mnt/c/Users/panda/.codex/recovery/Adaptive-rag-20261113-467df67775c0485fbcd23b50481ed14a.git/objects",
)
sys.path.insert(0, str(ROOT))
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import command  # noqa: E402


def check(name, argv):
    log = PRIVATE / (run_id + "-" + name + ".log")
    with log.open("x") as stream:
        result = subprocess.run(argv, stdout=stream, stderr=stream, env=os.environ.copy())
    return {"exit": result.returncode, "private_log": str(log)}


result = {}
command(MANIFEST, "up")
try:
    if action == "dependency":
        targets = [
            "research/docs/agent_engineering_upgrade/p4_dependency_integration/test_live_api.py::test_actual_api_dependency_outage_and_recovery"
        ]
    else:
        targets = ["tests", "research/docs/agent_engineering_upgrade"]
    junit = PRIVATE / (run_id + ".xml")
    result["pytest"] = check(
        "pytest",
        [
            PYTHON,
            "-m",
            PREFIX + "p4_final_acceptance.offline",
            "pytest",
            *targets,
            "-q",
            "--junitxml=" + str(junit),
        ],
    )
    if junit.exists():
        result["pytest"]["summary"] = [
            {
                k: v
                for k, v in s.attrib.items()
                if k in ["tests", "failures", "errors", "skipped", "time"]
            }
            for s in ET.parse(junit).getroot().iter("testsuite")
        ]
    if action != "dependency":
        result["legacy214"] = check(
            "legacy214",
            [
                PYTHON,
                "-m",
                PREFIX + "p4_final_acceptance.offline",
                PREFIX + "p4_dependency_integration.regress",
                run_id + "_legacy",
            ],
        )
        result["real_dev_mock"] = check(
            "real_dev_mock",
            [
                PYTHON,
                "-m",
                PREFIX + "p4_final_acceptance.offline",
                "pytest",
                "tests/unit/test_real_agent_dev.py",
                "tests/unit/test_paid_budget.py",
                "tests/unit/test_docker_bootstrap.py",
                "tests/unit/test_docker_compose.py",
                "-q",
            ],
        )
        result["ruff"] = check(
            "ruff",
            [
                str(Path(PYTHON).parent / "ruff"),
                "check",
                "app",
                "tests",
                "eval",
                "alembic",
                "research",
                "scripts/showcase.py",
            ],
        )
        result["mypy"] = check("mypy", [str(Path(PYTHON).parent / "mypy")])
        result["pip"] = check("pip", [PYTHON, "-m", "pip", "check"])
finally:
    command(MANIFEST, "stop")
    result["p4b_stopped_volumes_preserved"] = True
with (
    HERE / "evidence" / ("dependency-outage.json" if action == "dependency" else "regression.json")
).open("x") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
raise SystemExit(int(any(r.get("exit", 0) for r in result.values() if isinstance(r, dict))))
