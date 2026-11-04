"""Phase-local registration and preservation metadata; never initializes a project."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STATE = ROOT / "research/docs/agent_engineering_upgrade"


def initialize():
    registry = STATE / "feature-list.json"
    data = json.loads(registry.read_text(encoding="utf-8"))
    if "p2_quality" in data:
        raise RuntimeError("P2-Q already registered; resume, do not initialize")
    tasks = []
    definitions = [
        ("P2-QA", [], ["Durable bounded request replay tested", "Real interleaved paired evidence or explicit partial interruption", "Frozen source/Gold/config and cost/latency/errors retained"]),
        ("P2-QB", ["P2-QA"], ["All nine failures traced with first provable node", "Evidence-backed Memory fixes only; corrupt inputs not inferred", "Old12 unchanged regression; unseen dataset frozen before implementation"]),
        ("P2-QC", ["P2-QB"], ["Necessary versus redundant tool calls justified", "Fixed-Memory C0/C1 with owner7,longwindow,full80 and safety tests", "Minimal Planner/Fallback changes, independent attribution"]),
        ("P2-QD", ["P2-QC"], ["All pytest/Ruff/Mypy and four-source regression evidence", "Unseen evaluation after implementation freeze; failures retained", "Historical state/evidence and user files preserved; safe normal push"]),
    ]
    for name, deps, criteria in definitions:
        tasks.append(dict(TASK_ID=name, status="pending", passes=False, dependencies=deps, acceptance_criteria=criteria, evidence=[], commit_hash=None, next_action="Follow P2-Q_PLAN.md"))
    data["p2_quality"] = dict(phase="P2-Q", status="in_progress", baseline_commit="c45f509f5e4260c34818df9bf48f2807dd1338b4", tasks=tasks, budget=dict(http=350,tokens=300000,estimated_usd=3,concurrency=1), p3_started=False,p4_started=False)
    registry.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    with (STATE / "progress.txt").open("a",encoding="utf-8") as handle:
        handle.write("\nP2_Q_AUTHORIZED\nBASELINE=c45f509f5e4260c34818df9bf48f2807dd1338b4;remote verified\nWORKTREE=.worktrees/p2-quality;branch=codex/p2-quality;root user changes preserved\nBUDGET=350HTTP/300000tokens/estimatedUSD3;concurrency1;request replay mandatory\nDISCOVERY=Old heldout inputs contain literal ASCII question marks; investigate as infrastructure defect, never infer missing semantics\nNEXT_ACTION=QA request-ledger mocked verification then real pilot; unseen independently frozen.\n")
    paths = subprocess.check_output(["git","ls-tree","-r","--name-only","HEAD","research/docs/agent_engineering_upgrade"],cwd=ROOT,text=True).splitlines()
    records = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths if p not in {"research/docs/agent_engineering_upgrade/feature-list.json","research/docs/agent_engineering_upgrade/progress.txt"}}
    target=STATE/"p2_quality/preservation.json"
    target.write_text(json.dumps(dict(baseline="c45f509f5e4260c34818df9bf48f2807dd1338b4",historical_files=records),indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    initialize()
