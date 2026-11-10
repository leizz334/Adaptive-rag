"""Post-run evidence analysis; raw scores/Gold/traces are never rewritten."""

import json
import re
from collections import Counter

from research.docs.agent_engineering_upgrade.p3_experience_validation.manage import (
    HERE,
    ROOT,
    save,
    sha,
)


def differences(a, b, path=""):
    if type(a) is not type(b):
        return [dict(path=path, before=a, after=b)]
    if isinstance(a, dict):
        return [
            d
            for key in sorted(a.keys() | b.keys())
            for d in differences(a.get(key), b.get(key), path + "/" + key)
        ]
    if isinstance(a, list):
        if len(a) != len(b):
            return [dict(path=path + "/length", before=len(a), after=len(b))]
        return [
            d
            for i, (left, right) in enumerate(zip(a, b, strict=True))
            for d in differences(left, right, path + f"/{i}")
        ]
    return [] if a == b else [dict(path=path, before=a, after=b)]


def compare_behavior(a, b):
    raw = differences(a, b)
    fresh = [
        d
        for d in raw
        if re.fullmatch(r"/decisions/\d+/pending/action_id", d["path"])
        and all(
            isinstance(d[k], str) and re.fullmatch(r"act_[a-f0-9]{32}", d[k])
            for k in ("before", "after")
        )
    ]
    return dict(
        raw_equal=not raw,
        decision_equal=len(fresh) == len(raw),
        fresh_handle_differences=fresh,
        other_differences=[d for d in raw if d not in fresh],
    )


def main():
    run = HERE / "runs/20261110_B2_02"

    def read(path):
        return json.loads(path.read_bytes())

    result = read(run / "results.json")
    comparisons = []
    semantic = {}
    for arm in ("E0", "E1", "E2"):
        scores, environments = [], []
        for row in result["rows"]:
            captured = read(run / f"{row['case_id']}_{arm}.json")
            scores.extend(captured["answer_scores"])
            environments.append(
                captured["capture"]["results"][0]["metrics"].get("environment_state_correct")
            )
        semantic[arm] = dict(
            turns=len(scores),
            dimensions={
                key: dict(Counter(s[key] for s in scores))
                for key in (
                    "ANSWER_FACTUAL_CORRECTNESS",
                    "ANSWER_FAITHFULNESS",
                    "OVERALL_TASK_SUCCESS",
                    "ABSTENTION_CORRECTNESS",
                    "JUDGE_VALIDITY",
                )
            },
            complete_required_goals=sum(s["ANSWER_COMPLETENESS"] == 1 for s in scores),
            required_facts_matched=sum(
                f["matched"] and not f["contradiction"]
                for s in scores
                for f in s["facts"]
                if f["required"]
            ),
            required_fact_count=sum(f["required"] for s in scores for f in s["facts"]),
            environment_success=sum(v == 1 for v in environments),
        )
    for row in result["rows"]:
        arms = {a: read(run / f"{row['case_id']}_{a}.json") for a in ("E0", "E1", "E2")}
        comparisons.append(
            dict(
                case_id=row["case_id"],
                E0_E1=compare_behavior(arms["E0"]["canonical"], arms["E1"]["canonical"]),
                E0_E2=compare_behavior(arms["E0"]["canonical"], arms["E2"]["canonical"]),
                E0_E1_model_input_hashes_equal=[
                    c["supplied_sha256"] for c in arms["E0"]["provider_calls"]
                ]
                == [c["supplied_sha256"] for c in arms["E1"]["provider_calls"]],
                failure_reasons=arms["E0"]["capture"]["results"][0]["reasons"],
            )
        )
    frozen = read(HERE / "evidence/b2_freeze_v2.json")
    assert all(sha(ROOT / p) == h for p, h in frozen["files"].items())
    summary = dict(
        raw_E0_E1_divergence=result["shadow_divergence"],
        decision_E0_E1_divergence=sum(not c["E0_E1"]["decision_equal"] for c in comparisons),
        decision_E0_E2_divergence=sum(not c["E0_E2"]["decision_equal"] for c in comparisons),
        independent_family_set_matches=sum(r["selection_match"] is True for r in result["rows"]),
        independent_cases=result["cases"],
        semantic=semantic,
        comparisons=comparisons,
        interpretation="Only fresh pending confirmation handles normalized at exact typed paths; raw2 remains unchanged. Open answer semantics unknown; frozen Owner-refusal wording limitation retained.",
    )
    target = run / "post_run_analysis.json"
    assert not target.exists(), "Never overwrite analysis evidence"
    save(target, summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "comparisons"}))


if __name__ == "__main__":
    main()
