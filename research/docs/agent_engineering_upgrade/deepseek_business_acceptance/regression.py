"""Offline provider/security regressions: no completion requests or real credentials."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_business_acceptance"
PRIVATE = Path("/home/panda/.adaptive-rag-business-20261114")
env = os.environ.copy()
env.update(
    DEEPSEEK_API_KEY="",
    EMBEDDING_API_KEY="",
    REAL_AGENT_PAID_AUTHORIZED="false",
    EXPERIENCE_MEMORY_MODE="off",
)
argv = [
    sys.executable,
    "-m",
    "research.docs.agent_engineering_upgrade.p4_final_acceptance.offline",
    "pytest",
    "tests/unit/test_paid_budget.py",
    "tests/unit/test_usage_settlement.py",
    "tests/unit/test_real_agent_dev.py",
    "tests/unit/test_runtime_modes.py",
    "-q",
    "--junitxml=" + str(PRIVATE / "regression.xml"),
]
with (PRIVATE / "regression.log").open("x") as stream:
    result = subprocess.run(argv, env=env, stdout=stream, stderr=stream)
summary = [
    {
        k: v
        for k, v in suite.attrib.items()
        if k in {"tests", "errors", "failures", "skipped", "time"}
    }
    for suite in ET.parse(PRIVATE / "regression.xml").getroot().iter("testsuite")
]
evidence = {
    "command": argv[1:],
    "exit": result.returncode,
    "summary": summary,
    "paid_requests": 0,
    "network": "offline wrapper; MockTransport providers",
}
with (HERE / "evidence/D2-regression.json").open("x") as stream:
    json.dump(evidence, stream, indent=2)
print(json.dumps(evidence))
raise SystemExit(result.returncode)
