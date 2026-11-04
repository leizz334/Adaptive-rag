"""New immutable-output controls using unchanged P1/P2 scorers and fixtures."""

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
from pathlib import Path

from eval.memory_ablation import REFERENCE_IDS, long_window_case, run_arm, summarize
from eval.multiturn import load_scenarios

ROOT = Path(__file__).resolve().parents[4]
QUALITY = Path(__file__).resolve().parent


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


async def evaluate(output, unseen=False):
    if output.exists():
        raise RuntimeError("Existing output must be preserved; choose a new run directory")
    output.mkdir(parents=True)
    old, old_sha = load_scenarios(ROOT / "eval/dataset/agent_v2_extended.json")
    held, held_sha = load_scenarios(
        ROOT / "research/docs/agent_engineering_upgrade/p2_evidence/heldout_reference.json"
    )
    cases = old + held + [long_window_case()]
    unseen_cases = []
    if unseen:
        unseen_cases, _ = load_scenarios(QUALITY / "new_unseen.json")
        cases += unseen_cases
    digest = hashlib.sha256("".join(c.model_dump_json() for c in cases).encode()).hexdigest()
    config = dict(
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        app_hashes={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "app").rglob("*.py"))
        },
        original_sha256=old_sha,
        heldout_sha256=held_sha,
        combined_sha256=digest,
        provider="OFFLINE_RULE_AND_SCRIPTED_NOT_REAL_MODEL",
        real="NOT_RUN",
        temperature="FIXTURE",
        tracing=False,
        network="FORBIDDEN",
    )
    write(output / "experiment_config.json", config)
    groups = dict(
        original80={c.id for c in old},
        original7=REFERENCE_IDS,
        diagnostic12={c.id for c in held},
        long_window={"p2_long_window"},
        new_unseen={c.id for c in unseen_cases},
    )
    arms = []
    for mode, scripted in [("M0", True), ("M1", True), ("M2", True), ("M2", False)]:
        arm = await run_arm(cases, digest, mode=mode, scripted=scripted)
        arm["groups"] = {}
        for label, identifiers in groups.items():
            rows = [r for r in arm["results"] if r["case_id"] in identifiers]
            metrics = summarize(rows)
            calls = [call for row in rows for call in row["evidence"]["tool_calls"]]
            metrics["tool_calls"] = len(calls)
            metrics["calls_per_task"] = len(calls) / len(rows) if rows else None
            arm["groups"][label] = metrics
        arms.append(arm)
        write(output / "results.json", {"status": "RUNNING", "arms": arms})
        print(
            json.dumps(
                dict(
                    mode=mode,
                    scripted=scripted,
                    groups={k: f'{v["passed"]}/{v["cases"]}' for k, v in arm["groups"].items()},
                )
            ),
            flush=True,
        )
    write(output / "results.json", {"status": "COMPLETED_OFFLINE", "arms": arms})
    write(
        output / "validation.json",
        dict(frozen_gold_unchanged=True, no_network=True, real="NOT_RUN", completed_arms=len(arms)),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--unseen", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    asyncio.run(evaluate(args.output, args.unseen))
