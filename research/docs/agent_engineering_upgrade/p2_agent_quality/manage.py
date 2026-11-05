"""Append P2-R checkpoints to existing project state; never runs Initializer."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = HERE.parent
BASE = "09819352cc6df98b9f8cb42ffb56e9c8365b5793"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode())


def register():
    path=STATE/"feature-list.json"
    data=json.loads(path.read_bytes())
    if "p2_agent_quality" in data:
        raise RuntimeError("P2-R already registered; resume")
    goals=[
        ["Verify pushed0981935 and preserve all prior evidence/user edits", "Reexecute old16 with actual ordered node/context/plan/answer/DB capture; reproduce frozen metrics"],
        ["Classify all16 first causes versus propagated score symptoms", "Account for25extra tools and15/16environment; retain scorer disputes and offline/real distinctions"],
        ["Freeze >=24 diverse Chinese development and >=24 independently withheld blind cases", "UTF8/role/entity/fixture/Gold/legal-path/overlap gates; no blind inspection before candidate freeze"],
        ["Evidence-backed minimal generic Context/Planner/executor fixes with RED/GREEN", "Preserve live reads,owner,session,HITL,idempotency; no IDs/test-specific rules or newMemory/MultiAgent"],
        ["C0/context-only/planner-only/combined controls when distinct; fixedM2 and unchangedoldGold", "Original80/seven/old16/dev/longwindow/safety and blind only after source freeze; retain regressions"],
        ["Bounded realDeepSeek source-paired dev/blind evidence or honest partial stop", "Shared durable request budget, no uncertain replay; full usage/errors/latency/source/Prompt attribution"],
        ["Fullpytest/Ruffformatlint/Mypy and safety/provider/eval compatibility", "All old evidence and user work preserved; taskcommits and ordinary authorized push+lsremote verified; STOP"],
    ]
    tasks=[]
    for i,criteria in enumerate(goals):
        tasks.append(dict(TASK_ID=f"P2-R{i}",status="pending",passes=False,dependencies=[f"P2-R{i-1}"] if i else [],acceptance_criteria=criteria,evidence=[],commit_hash=None,next_action="Follow P2-R_PLAN.md"))
    data["p2_agent_quality"]=dict(phase="P2-R",status="in_progress",baseline_commit=BASE,baseline_remote_verified=BASE,prior_user_push_reconciled=True,tasks=tasks,budget=dict(http=420,tokens=420000,estimated_usd=3,per_scenario_http=24,concurrency=1),p3_started=False,p4_started=False)
    save(path,data)
    with (STATE/"progress.txt").open("ab") as stream:
        stream.write(b'\nP2_R_AUTHORIZED_2026_11_05\nBASELINE=09819352cc6df98b9f8cb42ffb56e9c8365b5793;actualorigin/codex/p2-qualityverified;prioruserpushreconciledinNEWphaseonly\nBRANCH=codex/p2-agent-quality;WORKTREE=.worktrees/p2-agent-quality;rootuserchangespreserved\nSCOPE=R0-R6continuous;noMemorylayers/ExperienceMemory/productMultiAgent;noP3/P4\nNEXT_ACTION=R0immutablebaseline+instrumentedold16reexecution;independentblind24authorwithheld.\n')
    paths=subprocess.check_output(["git","ls-tree","-r","--name-only",BASE,"research/docs/agent_engineering_upgrade"],cwd=ROOT,text=True).splitlines()
    frozen={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths if not p.endswith(("feature-list.json","progress.txt"))}
    user_root=Path("D:/Code/Adaptive-rag")
    user_paths=set(subprocess.check_output(["git","diff","--name-only"],cwd=user_root,text=True).splitlines()+subprocess.check_output(["git","ls-files","--others","--exclude-standard"],cwd=user_root,text=True).splitlines()+[".env"])
    users={p:hashlib.sha256((user_root/p).read_bytes()).hexdigest() for p in sorted(user_paths) if (user_root/p).is_file()}
    save(HERE/"evidence/preservation.json",dict(baseline=BASE,prior_artifacts=frozen,user_root=str(user_root),user_files=users,root_prior_artifacts={p:hashlib.sha256((user_root/p).read_bytes()).hexdigest() for p in frozen}))


def checkpoint(task_id,status,passes,evidence,next_action,**details):
    path=STATE/"feature-list.json"
    data=json.loads(path.read_bytes())
    task=next(t for t in data["p2_agent_quality"]["tasks"] if t["TASK_ID"]==task_id)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    for prior in data["p2_agent_quality"]["tasks"]:
        if prior["passes"] and prior["TASK_ID"]!=task_id and not prior["commit_hash"]:
            prior["commit_hash"]=head
    task.update(status=status,passes=passes,evidence=evidence,next_action=next_action,**details)
    save(path,data)
    with (STATE/"progress.txt").open("ab") as stream:
        stream.write((f"\n{task_id}={status};passes={passes};previous_checkpoint={head}\nEVIDENCE={';'.join(evidence)}\nNEXT_ACTION={next_action}\n").encode())


if __name__=="__main__":
    register()
