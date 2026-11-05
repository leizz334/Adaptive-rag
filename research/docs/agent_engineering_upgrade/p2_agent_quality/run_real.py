"""Bounded sequential coordinator; workers own request reservations and replay."""

import json
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE/"runs/20261105_R5_pairs_01"


def read(path):
    return json.loads(path.read_bytes())


def save(value):
    (RUN/"coordinator.json").write_bytes((json.dumps(value,indent=2)+"\n").encode())


def main():
    config=read(RUN/"experiment_config.json")
    state=read(RUN/"results.json")
    pilot=config["selected"][0]["id"]
    pilot_rows=[g for g in state["groups"] if g["case_id"]==pilot and g["rep"]==0]
    assert {g["variant"] for g in pilot_rows}=={"R0","R1"}
    assert not any(g["request_errors"] for g in pilot_rows)
    outcome=dict(status="RUNNING",completed_commands=[],planned_pairs=len(config["selected"]),repeat_policy="At most first development pair once, only if complete pair budget forecast fits")
    save(outcome)
    jobs=[]
    for i,item in enumerate(config["selected"]):
        jobs.extend((item["id"],v,0) for v in (("R0","R1") if i%2==0 else ("R1","R0")))
    jobs.extend((pilot,v,1) for v in ("R1","R0"))
    for case,variant,rep in jobs:
        current=read(RUN/"results.json")
        if any(g["case_id"]==case and g["variant"]==variant and g["rep"]==rep for g in current["groups"]):
            continue
        command=[sys.executable,"-B",str(HERE/"real_pairs.py"),"run-group","--source-root",config["roots"][variant],"--project-root",config["project_root"],"--run-dir",str(RUN),"--variant",variant,"--case-id",case,"--rep",str(rep),"--env-file",config["env_file"]]
        completed=subprocess.run(command,cwd=config["roots"][variant])
        outcome["completed_commands"].append(dict(case=case,variant=variant,rep=rep,exit_code=completed.returncode))
        if completed.returncode:
            outcome.update(status="STOPPED_INFRASTRUCTURE_OR_BUDGET",last_case=case,last_variant=variant)
            save(outcome)
            return completed.returncode
        group=next(g for g in read(RUN/"results.json")["groups"] if g["case_id"]==case and g["variant"]==variant and g["rep"]==rep)
        if group["status"]=="ERROR":
            outcome.update(status="STOPPED_HTTP_INFRASTRUCTURE",last_case=case,last_variant=variant)
            save(outcome)
            return 2
        save(outcome)
    outcome["status"]="COMPLETED_WITH_ONE_REPEAT_PAIR"
    save(outcome)
    print(json.dumps(outcome),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
