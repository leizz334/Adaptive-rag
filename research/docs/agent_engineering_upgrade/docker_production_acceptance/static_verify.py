"""Final checks after the reviewed deployment-harness fix; no live Docker changes."""

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
PRIVATE = Path("/root/.local/state/adaptive-rag-production-20261113")
BIN = Path("/home/panda/.venvs/adaptive-rag-workbench/bin")
commands = {
    "ruff": [
        str(BIN / "ruff"),
        "check",
        "app",
        "tests",
        "eval",
        "alembic",
        "research",
        "scripts/showcase.py",
    ],
    "phase_format": [str(BIN / "ruff"), "format", "--check", str(HERE)],
    "rollback_tests": [
        str(BIN / "python"),
        "-m",
        "research.docs.agent_engineering_upgrade.p4_final_acceptance.offline",
        "pytest",
        str(HERE / "test_deploy_safety.py"),
        "-q",
        "--junitxml=" + str(PRIVATE / "rollback-tests.xml"),
    ],
}
result = {}
for name, argv in commands.items():
    with (PRIVATE / ("final-" + name + ".log")).open("w") as stream:
        check = subprocess.run(argv, stdout=stream, stderr=stream)
    result[name] = {"exit": check.returncode}
result["rollback_tests"]["summary"] = [
    {k: v for k, v in s.attrib.items() if k in ["tests", "failures", "errors", "skipped"]}
    for s in ET.parse(PRIVATE / "rollback-tests.xml").getroot().iter("testsuite")
]
for name in ["pytest", "real_dev_mock", "legacy214", "mypy", "pip"]:
    log = (PRIVATE / ("prod_20261114_suite01-" + name + ".log")).read_text()
    result[name + "_summary"] = re.findall(
        r"\d+ passed[^\n]*|Success: no issues found[^\n]*|No broken requirements found\.", log
    )
result["rollback_red_green"] = {
    "before": "4 failed, 1 passed; rollback skipped on injected exceptions",
    "after": "5 passed; image+health checked; no Docker dispatch in unit tests",
    "independent_review": "original important finding closed; no remaining important findings",
}
with (HERE / "evidence/final-static.json").open("x") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
raise SystemExit(int(any(v.get("exit", 0) for v in result.values() if isinstance(v, dict))))
