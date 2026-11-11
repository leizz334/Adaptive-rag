"""P4-C immutable files and common synthetic experiment configuration."""

import hashlib
import json
from pathlib import Path

from research.docs.agent_engineering_upgrade.p2_quality.real import SafetyStop

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = HERE / "runs/ubuntu_C_20261111_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_freeze():
    frozen = json.loads((HERE / "freeze.json").read_bytes())
    if any(sha(ROOT / path) != digest for path, digest in frozen["hashes"].items()):
        raise SafetyStop("frozen application/dataset/scorer/harness drift; no paid dispatch")
    return frozen
