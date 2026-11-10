"""Fresh P0-P3 strict compatibility under the P4-A candidate; no paid calls."""

import asyncio
import json
import logging

from eval.memory_ablation import long_window_case, run_arm, summarize
from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs import business_clock
from research.docs.agent_engineering_upgrade.p4_api_e2e.manage import HERE, ROOT, save


async def main():
    output = HERE / "runs/20261110_A2_legacy_01"
    output.mkdir(parents=True, exist_ok=False)
    paths = dict(
        original80=ROOT / "eval/dataset/agent_v2_extended.json",
        old16=HERE.parent / "p2_quality/new_unseen.json",
        former_development30=HERE.parent / "p2_agent_quality/datasets/development.json",
        former_holdout33=HERE.parent / "p2_agent_quality/datasets/blind_holdout.json",
        development24=HERE.parent / "p2_answer_reliability/datasets/development.json",
        holdout30=HERE.parent / "p2_answer_reliability/datasets/holdout.json",
    )
    groups, regressions = {}, []
    for name, path in list(paths.items()) + [("long_window", None)]:
        cases, digest = load_scenarios(path) if path else ([long_window_case()], "long-window")
        with business_clock("2026-11-05T00:00:00+00:00"):
            raw = await run_arm(cases, digest, mode="M2", scripted=True)
        save(output / f"{name}.json", raw)
        groups[name] = summarize(raw["results"])
        previous = json.loads(
            (
                HERE.parent / "p3_experience_validation/runs/20261110_B3_legacy_01" / f"{name}.json"
            ).read_bytes()
        )
        passes = {r["case_id"] for r in raw["results"] if r["status"] == "PASS"}
        regressions.extend(
            dict(dataset=name, case_id=r["case_id"])
            for r in previous["results"]
            if r["status"] == "PASS" and r["case_id"] not in passes
        )
        print(
            json.dumps(dict(group=name, passed=groups[name]["passed"], cases=groups[name]["cases"]))
        )
    save(
        output / "results.json",
        dict(
            groups=groups,
            regressions=regressions,
            model="OFFLINE_SCRIPTED_NOT_REAL_LLM",
            new_http=0,
            new_tokens=0,
            experience_active=False,
        ),
    )


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(main())
