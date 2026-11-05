"""Fixed-M2 offline source controls; run from each source worktree with parent on sys.path."""

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
from pathlib import Path

import app
from eval.memory_ablation import REFERENCE_IDS, long_window_case, run_arm, summarize
from eval.multiturn import load_scenarios

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
SOURCE = Path(app.__file__).resolve().parents[1]


def save(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def metrics(rows, cases):
    value = summarize(rows)
    turns = [t for r in rows for t in r["evidence"]["turns"]]
    value.update(
        trajectory_validity=sum(t["scores"]["trajectory_valid"] for t in turns) / len(turns)
        if turns
        else None,
        redundant_tool_calls=sum(t["scores"]["unnecessary_tool_calls"] for t in turns),
        tool_calls=sum(len(r["evidence"]["tool_calls"]) for r in rows),
        failure_cases=[
            dict(id=r["case_id"], reasons=r["reasons"]) for r in rows if r["status"] != "PASS"
        ],
    )
    fresh_required = fresh_correct = 0
    for row in rows:
        case = cases[row["case_id"]]
        for i, turn in enumerate(case.turns):
            if "business_rejected" in turn.expected_failures:
                continue
            for wanted in turn.trajectory.required:
                if wanted.name not in {"get_order", "track_shipment", "get_order_items"}:
                    continue
                fresh_required += 1
                found = [
                    c
                    for c in row["evidence"]["tool_calls"]
                    if c["turn"] == i
                    and c["name"] == wanted.name
                    and c["success"]
                    and all(c["arguments"].get(k) == v for k, v in wanted.arguments.items())
                ]
                fresh_correct += bool(
                    found
                    and all(
                        c["output"].get("status")
                        == turn.state_changes[wanted.arguments["order_id"]]
                        for c in found
                    )
                    if wanted.name == "get_order"
                    and wanted.arguments.get("order_id") in turn.state_changes
                    else found
                )
    value.update(
        fresh_observation_correct=fresh_correct,
        fresh_observation_required=fresh_required,
        fresh_observation_accuracy=fresh_correct / fresh_required if fresh_required else None,
    )
    return value


async def evaluate(output, label, blind=False, rule=False):
    if output.exists():
        raise RuntimeError("Use a new output directory; preserve previous controls")
    if blind and not (HERE / "evidence/candidate_freeze.json").exists():
        raise RuntimeError("Blind data cannot run before candidate freeze")
    original, old_sha = load_scenarios(PROJECT / "eval/dataset/agent_v2_extended.json")
    old16, old16_sha = load_scenarios(HERE.parent / "p2_quality/new_unseen.json")
    dev, dev_sha = load_scenarios(HERE / "datasets/development.json")
    held = []
    blind_sha = None
    if blind:
        held, blind_sha = load_scenarios(HERE / "datasets/blind_holdout.json")
    long = long_window_case()
    cases = original + old16 + dev + [long] + held
    by_id = {c.id: c for c in cases}
    assert len(by_id) == len(cases)
    digest = hashlib.sha256("".join(c.model_dump_json() for c in cases).encode()).hexdigest()
    output.mkdir(parents=True)
    config = dict(
        label=label,
        git_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True
        ).strip(),
        source_root=str(SOURCE),
        app_hashes={
            p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((SOURCE / "app").rglob("*.py"))
        },
        eval_hashes={
            p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((SOURCE / "eval").rglob("*.py"))
        },
        data=dict(
            original80=old_sha,
            old16=old16_sha,
            development=dev_sha,
            blind=blind_sha,
            combined=digest,
        ),
        mode="M2",
        provider="OFFLINE_RULE" if rule else "OFFLINE_SCRIPTED",
        real="NOT_RUN",
        network="FORBIDDEN",
        tracing=False,
        temperature="FIXTURE: production node schedule held constant",
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    save(output / "experiment_config.json", config)
    arm = await run_arm(cases, digest, mode="M2", scripted=not rule)
    scopes = dict(
        original80={c.id for c in original},
        original7=REFERENCE_IDS,
        old16={c.id for c in old16},
        development={c.id for c in dev},
        long_window={long.id},
        blind={c.id for c in held},
    )
    arm["groups"] = {
        name: metrics([r for r in arm["results"] if r["case_id"] in ids], by_id)
        for name, ids in scopes.items()
    }
    save(output / "results.json", dict(status="COMPLETED_OFFLINE", label=label, arm=arm))
    save(
        output / "validation.json",
        dict(
            status="PASS_EXECUTION",
            source_hashes_recorded=True,
            gold_unchanged=True,
            paid_api_calls=0,
            blind_evaluated_after_freeze=blind,
        ),
    )
    print(
        json.dumps(
            dict(
                label=label,
                groups={k: f'{v["passed"]}/{v["cases"]}' for k, v in arm["groups"].items()},
                safety={k: len(v["safety_violations"]) for k, v in arm["groups"].items()},
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--rule", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    asyncio.run(evaluate(args.output, args.label, args.blind, args.rule))
