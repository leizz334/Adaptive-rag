"""Read saved completions and score copies; never invokes a model or Agent."""

import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_agent_quality.benchmark import metrics
from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import HERE, save
from research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs import (
    Ledger,
    score_captured,
)

PARENT = HERE / "runs/20261105_S6_pairs_02"
RUN = HERE / "runs/20261108_S6_pairs_03"


def read(path):
    return json.loads(path.read_bytes())


def verdict(scores):
    states = [s["OVERALL_TASK_SUCCESS"] for s in scores]
    return (
        "FAIL"
        if "FAIL" in states
        else "PASS"
        if states and set(states) == {"PASS"}
        else "NOT_ASSESSED"
    )


def analyze():
    config = read(RUN / "experiment_config.json")
    ledger = Ledger(RUN, pricing=config["pricing"])
    groups = []
    cases = {}
    final_answers = []
    judge_states = []
    for root in (PARENT, RUN):
        cfg, result = read(root / "experiment_config.json"), read(root / "results.json")
        for data in cfg["datasets"].values():
            loaded, _ = load_scenarios(Path(data["path"]))
            cases.update({c.id: c for c in loaded})
        for group in result["groups"]:
            capture = read(root / "captures" / (group["group"].replace(":", "_") + ".json"))
            for turn in capture["traces"][0]["turns"]:
                final_answers.append(
                    (turn.get("response") or {}).get(
                        "answer", turn.get("final_state", {}).get("final_answer", "")
                    )
                )
                for node in turn["nodes"]:
                    if node["node"] == "check_faithfulness":
                        judged = node.get("output", {}).get("extra", {}).get("faithfulness")
                        if judged:
                            judge_states.append(
                                dict(
                                    variant=group["variant"], case_id=group["case_id"], value=judged
                                )
                            )
            row = dict(group)
            row["measurement"] = (
                "V21_LOCAL_RESCORING_OF_V20_PILOT" if root == PARENT else "V21_FROZEN_VALIDATION"
            )
            if root == PARENT:
                capture = read(root / "captures" / (group["group"].replace(":", "_") + ".json"))
                gold = read(Path(cfg["datasets"][group["split"]]["answers_path"]))[group["case_id"]]
                row["answer_scores"] = score_captured(capture, gold, adapter="v21")
            groups.append(row)
    paired = sorted(
        {
            g["case_id"]
            for g in groups
            if all(
                any(h["case_id"] == g["case_id"] and h["variant"] == v for h in groups)
                for v in ("R0", "R1")
            )
        }
    )
    arms = {}
    for arm in ("R0", "R1"):
        arms[arm] = {}
        for split in ("all", "development", "blind"):
            scoped = [
                g
                for g in groups
                if g["variant"] == arm
                and g["case_id"] in paired
                and (split == "all" or g["split"] == split)
            ]
            value = metrics([g["raw_driver_result"] for g in scoped], cases) if scoped else {}
            for inherited_placeholder in (
                "paid_tokens",
                "real_model_tokens",
                "scripted_calls",
                "estimated_input_utf8_bound",
            ):
                value.pop(inherited_placeholder, None)
            scores = [s for g in scoped for s in g["answer_scores"]]
            value.update(
                case_answers=dict(Counter(verdict(g["answer_scores"]) for g in scoped)),
                turn_answers={
                    key: dict(Counter(s[key] for s in scores))
                    for key in (
                        "ANSWER_FACTUAL_CORRECTNESS",
                        "ANSWER_FAITHFULNESS",
                        "OVERALL_TASK_SUCCESS",
                    )
                },
                full_verified_goal_coverage=sum(
                    s["VERIFIED_GOAL_COVERAGE_LOWER_BOUND"] == 1 for s in scores
                ),
                answer_turns=len(scores),
                completeness_verified=[s["ANSWER_COMPLETENESS"] for s in scores],
                goal_coverage_lower_bounds=[
                    s["VERIFIED_GOAL_COVERAGE_LOWER_BOUND"] for s in scores
                ],
                confirmed_goal_omissions=sum(len(s["missing_subgoals"]) for s in scores),
                unresolved_goals=sum(len(s["unresolved_subgoals"]) for s in scores),
                semantic_human_calibration="NOT_RUN",
            )
            arms[arm][split] = value
    latencies = sorted(r["latency_ms"] for r in ledger.rows if r.get("latency_ms") is not None)
    conversions = [
        {
            "case_id": case,
            **{
                arm: {
                    "tool_state": g["status"],
                    "answer": verdict(g["answer_scores"]),
                    "reasons": g["raw_driver_result"]["reasons"],
                }
                for arm in ("R0", "R1")
                for g in groups
                if g["case_id"] == case and g["variant"] == arm
            },
        }
        for case in paired
    ]
    diagnostics = dict(
        truncations=sum(r.get("model_error") == "truncated" for r in ledger.rows),
        model_errors=dict(
            Counter(str(r["model_error"]) for r in ledger.rows if r.get("model_error"))
        ),
        http_errors=sum(r.get("http_status") not in (None, 200) for r in ledger.rows),
        uncertain_requests=sum(r.get("status") != "RESPONSE" for r in ledger.rows),
        prompt_tokens=sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in ledger.rows),
        completion_tokens=sum(
            (r.get("usage") or {}).get("completion_tokens", 0) for r in ledger.rows
        ),
        total_http_latency_ms=sum(latencies),
        mean_http_latency_ms=mean(latencies) if latencies else None,
        p95_http_latency_ms=latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
        judge_truncations=sum(
            r.get("model_error") == "truncated" and r.get("stage") == "judge" for r in ledger.rows
        ),
        truncations_by_arm_and_stage=dict(
            Counter(
                r["group"].split(":")[1] + ":" + r.get("stage", "unknown")
                for r in ledger.rows
                if r.get("model_error") == "truncated"
            )
        ),
        false_model_unconfigured_answers=sum(
            any(p in answer for p in ("未配置生成模型", "未配置大模型")) for answer in final_answers
        ),
        judge_node_states=judge_states,
    )
    value = dict(
        status=read(RUN / "results.json")["status"],
        paired_cases=len(paired),
        arms=arms,
        conversions=conversions,
        budget=ledger.totals(),
        diagnostics=diagnostics,
        groups=groups,
        safety_scope="Frozen strict contract plus full unit security regressions; no general semantic safety certification",
        human_calibration="NOT_RUN",
        accounting="Run03 includes unchanged11request parent prefix once; no double count",
        open_semantics="NOT_ASSESSED",
    )
    save(HERE / "evidence/s6_real_aggregate_v21.json", value)
    print(json.dumps({k: value[k] for k in ("status", "paired_cases", "budget", "diagnostics")}))
    return value


if __name__ == "__main__":
    analyze()
