"""Derive case-level answer metrics from unchanged frozen per-turn results."""

import json
from collections import Counter, defaultdict

from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import HERE, save


def aggregate(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["case_id"]].append(row["score"]["OVERALL_TASK_SUCCESS"])
    verdicts = {
        identifier: "FAIL"
        if "FAIL" in statuses
        else "PASS"
        if set(statuses) == {"PASS"}
        else "NOT_ASSESSED"
        for identifier, statuses in grouped.items()
    }
    return dict(
        cases=len(grouped),
        overall_cases=dict(Counter(verdicts.values())),
        case_verdicts=verdicts,
        missing_required_subgoals=sum(len(r["score"].get("missing_subgoals", [])) for r in rows),
        unassessed_subgoals=sum(len(r["score"].get("unknown_subgoals", [])) for r in rows),
    )


def main():
    results = {}
    for arm in ("S0", "S1", "S2", "S3"):
        results[arm] = {}
        for group in ("development24", "holdout30"):
            rows = json.loads(
                (HERE / f"runs/s5_offline_fixedclock/{arm}/{group}/answers.json").read_bytes()
            )
            results[arm][group] = aggregate(rows)
    save(
        HERE / "evidence/s5_case_metrics.json",
        dict(
            method="FAIL if any turnFAIL;PASS only all turnsPASS;otherwiseNOT_ASSESSED;frozen per-turnscores unchanged",
            arms=results,
        ),
    )
    print(
        json.dumps(
            {a: {g: m["overall_cases"] for g, m in groups.items()} for a, groups in results.items()}
        )
    )


if __name__ == "__main__":
    main()
