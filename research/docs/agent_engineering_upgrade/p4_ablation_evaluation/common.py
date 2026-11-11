import hashlib
import json
import os
from contextvars import ContextVar
from importlib.metadata import version
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import SafetyStop

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = HERE / "runs/ubuntu_D_20261111_01"
ARM = ContextVar("p4d_arm", default="BASE")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_freeze():
    path = Path(os.environ["P4D_FREEZE_FILE"]).resolve()
    if path.parent != HERE or path.name not in ["freeze_d0.json", "freeze_d2.json"]:
        raise SafetyStop("unowned freeze")
    d = json.loads(path.read_bytes())
    if any(sha(ROOT / p) != h for p, h in d["hashes"].items()):
        raise SafetyStop("source/data/scorer drift closes paid admission")
    if any(version(name) != expected for name, expected in d.get("packages", {}).items()):
        raise SafetyStop("frozen dependency versions changed")
    return d
