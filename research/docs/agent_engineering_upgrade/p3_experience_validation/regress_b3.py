"""Fresh legacy M2 regression to new P3-B evidence only; no live dependencies."""

import asyncio
import json
import logging

from eval.memory_ablation import long_window_case, run_arm, summarize
from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs import business_clock
from research.docs.agent_engineering_upgrade.p3_experience_validation.manage import HERE, ROOT, save
from research.docs.agent_engineering_upgrade.p3_experience_validation.run_experiment import (
    SEED_CLOCK,
)


async def main():
    output = HERE / "runs/20261110_B3_legacy_01"
    output.mkdir(parents=True, exist_ok=False)
    paths = dict(
        original80=ROOT / "eval/dataset/agent_v2_extended.json",
        old16=HERE.parent / "p2_quality/new_unseen.json",
        former_development30=HERE.parent / "p2_agent_quality/datasets/development.json",
        former_holdout33=HERE.parent / "p2_agent_quality/datasets/blind_holdout.json",
        development24=HERE.parent / "p2_answer_reliability/datasets/development.json",
        holdout30=HERE.parent / "p2_answer_reliability/datasets/holdout.json",
    )
    results, regressions = {}, []
    for name, path in list(paths.items()) + [("long_window", None)]:
        cases, digest = (
            load_scenarios(path) if path else ([long_window_case()], "long-window-contract")
        )
        with business_clock(SEED_CLOCK):
            raw = await run_arm(cases, digest, mode="M2", scripted=True)
        save(output / f"{name}.json", raw)
        results[name] = summarize(raw["results"])
        previous = json.loads(
            (
                HERE.parent / "p3_experience_shadow/runs/20261109_regression_01" / f"{name}.json"
            ).read_bytes()
        )
        passed = {r["case_id"] for r in raw["results"] if r["status"] == "PASS"}
        regressions.extend(
            dict(dataset=name, case_id=r["case_id"])
            for r in previous["results"]
            if r["status"] == "PASS" and r["case_id"] not in passed
        )
        print(
            json.dumps(
                dict(group=name, passed=results[name]["passed"], cases=results[name]["cases"])
            )
        )
    save(
        output / "results.json",
        dict(
            groups=results,
            regressions=regressions,
            new_http=0,
            new_tokens=0,
            memory="M2",
            experience_mode="off",
            provider="OFFLINE_SCRIPTED",
            seed_clock=SEED_CLOCK,
        ),
    )


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(main())
