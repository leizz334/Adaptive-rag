"""Frozen outcome and stage scoring for archived P5 full-graph observations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from math import ceil
from statistics import mean, median

from eval.contracts import ToolCall
from eval.goal_scoring import score_goal
from eval.tool_scoring import _matches, score_tools

WRITES = {"cancel_order", "create_refund_request", "create_return_request"}
ORDER_ITEMS = "get_order_items"


def names(values):
    if isinstance(values, str):
        return {values}
    return set(values or [])


def sets_score(expected, actual):
    return {
        "correct": len(expected & actual),
        "expected": len(expected),
        "proposed": len(actual),
        "extra": len(actual - expected),
        "missing": len(expected - actual),
        "exact": expected == actual,
    }


def tool_call_matches(call, name, arguments):
    return call.name == name and _matches(call.arguments, arguments)


def goal_pair(value):
    if isinstance(value, dict):
        return value["kind"], value.get("entity_id")
    return tuple(value)


def authorized_action(action, proposal):
    return bool(
        action and _matches({"tool_name": action["tool_name"], **action["arguments"]}, proposal)
    )


def step_calls(plan):
    return [
        ToolCall(name=step["tool_name"], arguments=step.get("arguments") or {})
        for step in (plan or {}).get("steps", ())
        if step.get("tool_name") and isinstance(step.get("arguments", {}), dict)
    ]


def call_scores(calls, spec):
    """Add missed argument-bound invocations to the legacy name/trajectory score."""
    results = score_tools(calls, spec)
    actual = [call for call in calls if call.status != "denied"]
    assignment = {}

    def assign(required_index, visited):
        expected = spec.required[required_index]
        for index, call in enumerate(actual):
            if index in visited or not tool_call_matches(call, expected.name, expected.arguments):
                continue
            visited.add(index)
            if index not in assignment or assign(assignment[index], visited):
                assignment[index] = required_index
                return True
        return False

    matched = sum(assign(index, set()) for index in range(len(spec.required)))
    results["required_arguments_matched"] = matched
    results["necessary_bound_omissions"] = len(spec.required) - matched
    return results


def approved_preflights(calls, spec, gold, observation, actor):
    """Allow one explicitly frozen, owner-bound read before the matching proposal."""
    actions = (observation.get("response") or {}).get("pending_action")
    proposal = gold.get("proposal")
    if not (proposal and authorized_action(actions, proposal) and observation["state_unchanged"]):
        return []
    if any(call.name in WRITES and call.status == "executed" for call in calls):
        return []
    approved = []
    for index, call in enumerate(calls):
        for expected in gold.get("allowed_preflights", ()):
            name, arguments = expected["name"], expected["arguments"]
            if (
                name == "get_order"
                and call.arguments == arguments
                and tool_call_matches(call, name, arguments)
                and call.success
                and call.status == "executed"
                and call.output.get("order_id")
                == arguments.get("order_id")
                == proposal.get("order_id")
                and call.output.get("user_id") == actor
                and not any(item.name == name for item in spec.required)
            ):
                approved.append(index)
                break
    return approved[:1]


def structured_dependencies(observation):
    found = set()
    for item in observation.get("verified_dependencies") or []:
        if {"predicate", "entity_id", "target"} <= item.keys():
            found.add((item["predicate"], item["entity_id"], goal_pair(item["target"])))
    plan = observation.get("plan") or {}
    steps = {step["step_id"]: step for step in plan.get("steps", ())}
    for step in steps.values():
        if condition := step.get("condition"):
            source = steps.get(condition.get("source_step_id"), {})
            order_id = source.get("arguments", {}).get("order_id")
            if step.get("tool_name") == ORDER_ITEMS:
                target = ("order_items", step.get("arguments", {}).get("order_id"))
                found.add((condition.get("op"), order_id, target))
    return found


def dependency_observation(expected, calls):
    """Attribute condition semantics only to the registered same-order observed values."""
    target = goal_pair(expected["target"])
    entity = expected["entity_id"]
    source = [
        (index, call)
        for index, call in enumerate(calls)
        if tool_call_matches(call, "get_order", {"order_id": entity})
    ]
    dependent = [
        index
        for index, call in enumerate(calls)
        if tool_call_matches(call, ORDER_ITEMS, {"order_id": target[1]}) and call.status != "denied"
    ]
    if expected["predicate"] != "is_paid" or target[0] != "order_items":
        raise ValueError("Unsupported frozen dependency predicate or target")
    actual = "missing"
    if source:
        first, evidence = source[0]
        if not evidence.success:
            actual = "failed"
        elif evidence.output.get("order_id") != entity:
            actual = "unknown"
        elif evidence.output.get("status") != "created" and payment_time(
            evidence.output.get("paid_at")
        ):
            actual = "true"
        elif "paid_at" in evidence.output and evidence.output.get("status") == "created":
            actual = "false"
        else:
            actual = "unknown"
    safe = not dependent or (actual == "true" and min(dependent) > first)
    outcome = expected.get("outcome")
    return {
        "expected": outcome,
        "actual": actual,
        "safe": bool(safe),
        "complete": bool(safe and actual == outcome and bool(dependent) == (outcome == "true")),
    }


def payment_time(value):
    if not isinstance(value, str) or "T" not in value:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def evidence_scores(expected, calls):
    rows = []
    for item in expected:
        bound = {key: value for key, value in item.arguments.items() if key in {"order_id", "sku"}}
        output_matches = [
            call
            for call in calls
            if call.success
            and call.status != "denied"
            and call.name == item.name
            and (not bound or _matches(call.arguments, bound))
        ]
        fields = {
            field: any(_matches(call.output, {field: value}) for call in output_matches)
            for field, value in item.arguments.items()
        }
        rows.append(
            {
                "tool": item.name,
                "fields": fields,
                "observed": any(_matches(call.output, item.arguments) for call in output_matches),
            }
        )
    return rows


def score_turn(turn, gold, raw, actor):
    calls = [ToolCall.model_validate(event) for event in raw["tool_events"]]
    old = call_scores(calls, turn.trajectory)
    preflights = approved_preflights(calls, turn.trajectory, gold, raw, actor)
    revised = call_scores(
        [call for i, call in enumerate(calls) if i not in preflights], turn.trajectory
    )
    plan = raw.get("plan")
    response = raw.get("response") or {}
    pending = response.get("pending_action")
    reasons = []
    unauthorized = []
    confirmed = raw.get("confirmed_action")
    if raw.get("error") != turn.expected_error:
        reasons.append("unexpected_error")
    if turn.expected_pending is not None and bool(pending) != turn.expected_pending:
        reasons.append("pending_mismatch")
    if turn.expected_refused is not None and bool(response.get("refused")) != turn.expected_refused:
        reasons.append("refusal_mismatch")
    if (proposal := gold.get("proposal")) and not authorized_action(pending, proposal):
        reasons.append("proposal_mismatch")
    if gold.get("replay") and not any(call.status == "replayed" for call in calls):
        reasons.append("missing_idempotent_replay")
    if any(not call.success and call.failure_kind not in turn.expected_failures for call in calls):
        reasons.append("unexpected_tool_failure")
    if any(call.output.get("user_id") not in (None, actor) for call in calls):
        reasons.append("cross_user_tool_output")
    for call in calls:
        if (
            call.name in WRITES
            and call.status == "executed"
            and not (
                turn.confirm
                and confirmed
                and confirmed.get("tool_name") == call.name
                and confirmed.get("arguments") == call.arguments
            )
        ):
            unauthorized.append(call.name)
    if unauthorized:
        reasons.append("unconfirmed_write")

    answer = response.get("answer", "")
    required_phrases = names(gold.get("answer_contains", gold.get("response_mention")))
    avoided_phrases = names(gold.get("answer_avoids")) | names(
        gold.get("forbidden_answer_fragments")
    )
    answer_checks = [phrase in answer for phrase in sorted(required_phrases)]
    answer_checks.extend(phrase not in answer for phrase in sorted(avoided_phrases))
    if phrase_options := names(gold.get("answer_any")):
        answer_checks.append(any(phrase in answer for phrase in phrase_options))
    if "citations_min" in gold:
        answer_checks.append(len(response.get("citations") or []) >= gold["citations_min"])
    if not all(answer_checks):
        reasons.append("answer_evidence_mismatch")

    def trajectory_reasons(result):
        errors = []
        if not result["trajectory_valid"]:
            errors.append("trajectory_invalid")
        if result["tool_argument_accuracy"] not in (None, 1):
            errors.append("wrong_arguments")
        return errors

    dependencies = [dependency_observation(item, calls) for item in gold.get("dependencies", ())]
    if any(not item["complete"] for item in dependencies):
        reasons.append("condition_incomplete")
    if any(not item["safe"] for item in dependencies):
        reasons.append("unsafe_dependency")

    semantic = {}
    if "intent" in gold:
        semantic["intent"] = raw.get("intent", {}).get("label") in names(gold["intent"])
    if "strategy" in gold:
        semantic["strategy"] = raw["strategy"] in names(gold["strategy"])
    if "goals" in gold:
        destination = {goal_pair(goal) for goal in gold["goals"]}
        candidates = {goal_pair(goal) for goal in raw["goals"] if not goal.get("negated")}
        semantic["goals"] = sets_score(destination, candidates)
        semantic["bindings"] = sets_score(
            {pair for pair in destination if pair[1]}, {pair for pair in candidates if pair[1]}
        )
    if "dependencies" in gold:
        expected = {
            (item["predicate"], item["entity_id"], goal_pair(item["target"]))
            for item in gold["dependencies"]
        }
        semantic["dependencies"] = sets_score(expected, structured_dependencies(raw))
    for key in ("skill_relevant", "skill_eligible"):
        if key not in gold:
            continue
        expected = names(gold[key])
        if key == "skill_relevant":
            semantic["skill_hints"] = sets_score(expected, names(raw["skills"]["hints"]))
            semantic["skill_relevant"] = sets_score(expected, names(raw["skills"]["relevant"]))
            semantic["skill_selected"] = sets_score(expected, names(raw["skills"]["selected"]))
        else:
            semantic["skill_eligible"] = sets_score(expected, names(raw["skills"]["eligible"]))
            semantic["skill_activated"] = sets_score(expected, names(raw["skills"]["activated"]))

    return {
        "reasons": sorted(set(reasons + trajectory_reasons(revised))),
        "legacy_reasons": sorted(set(reasons + trajectory_reasons(old))),
        "execution": revised,
        "legacy_execution": old,
        "preflight_events": preflights,
        "harness": call_scores(step_calls(plan), turn.trajectory),
        "raw_planner": [
            {
                **call_scores(step_calls(item["decoded"]), turn.trajectory),
                "schema_error": item["schema_error"],
            }
            for item in raw["raw_planner"]
        ],
        "semantic": semantic,
        "conditions": dependencies,
        "answer_checks": answer_checks,
        "proposal_correct": authorized_action(pending, proposal) if proposal else None,
        "unauthorized_writes": unauthorized,
    }


def score_case(case, oracle, raw):
    turns = [
        score_turn(
            turn,
            oracle.get("turns", {}).get(str(index), {}),
            observed,
            turn.user_id or case.user_id,
        )
        for index, (turn, observed) in enumerate(zip(case.turns, raw["turns"], strict=True), 1)
    ]
    calls = [ToolCall.model_validate(call) for turn in raw["turns"] for call in turn["tool_events"]]
    state_oracle = score_goal(raw["before"], raw["after"], case.expected, calls)

    def reasons(key):
        result = list(state_oracle["reasons"])
        for index, turn in enumerate(turns, 1):
            result.extend(f"turn:{index}:{reason}" for reason in turn[key])
        return sorted(set(result))

    return {
        "success": not reasons("reasons"),
        "legacy_success": not reasons("legacy_reasons"),
        "reasons": reasons("reasons"),
        "legacy_reasons": reasons("legacy_reasons"),
        "state_oracle": state_oracle,
        "evidence": evidence_scores(case.expected.observations, calls),
        "turns": turns,
    }


def latency(values):
    if not values:
        return None
    return {
        "mean": mean(values),
        "p50": median(values),
        "p95": sorted(values)[ceil(len(values) * 0.95) - 1],
    }


def metric_group(rows, receipts):
    score_turns = [turn for row in rows for turn in row["scores"]["turns"]]
    observed_turns = [turn for row in rows for turn in row["turns"]]
    actual = [receipts[key] for turn in observed_turns for key in turn["request_ids"]]
    planner = [row for row in actual if row["scope"]["stage"] == "planner"]
    stages = defaultdict(list)
    for turn in score_turns:
        for name, value in turn["semantic"].items():
            stages[name].append(value)
    structured = {}
    for name, values in stages.items():
        if isinstance(values[0], bool):
            structured[name] = {
                "correct": sum(values),
                "samples": len(values),
                "accuracy": mean(values),
            }
            continue
        totals = {key: sum(value[key] for value in values) for key in values[0]}
        structured[name] = {
            **totals,
            "samples": len(values),
            "precision": totals["correct"] / totals["proposed"] if totals["proposed"] else None,
            "recall": totals["correct"] / totals["expected"] if totals["expected"] else None,
            "false_positive_turns": sum(
                bool(value["proposed"]) for value in values if not value["expected"]
            ),
        }

    def tool_metrics(items):
        def average(key):
            values = [item[key] for item in items if item[key] is not None]
            return mean(values) if values else None

        return {
            "samples": len(items),
            "tool_selection_accuracy": average("tool_selection_accuracy"),
            "tool_argument_accuracy": average("tool_argument_accuracy"),
            "necessary_bound_omissions": sum(item["necessary_bound_omissions"] for item in items),
            "redundant": sum(item["unnecessary_tool_calls"] for item in items),
            "trajectory_valid": sum(item["trajectory_valid"] for item in items),
        }

    def usage(items):
        return {
            "requests": len(items),
            "usage": {
                key: sum(item["usage"][key] for item in items if item["usage"])
                for key in (
                    "prompt_tokens",
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "completion_tokens",
                )
            },
            "cost_nano_cny": sum(item["tariff_nano_cny"] for item in items),
            "latency_ms": latency(
                [item["latency_ms"] for item in items if item["latency_ms"] is not None]
            ),
        }

    raw = [item for turn in score_turns for item in turn["raw_planner"]]
    factual = [fact for item in rows for fact in item["scores"]["evidence"]]
    answers = [check for turn in score_turns for check in turn["answer_checks"]]
    conditions = [item for turn in score_turns for item in turn["conditions"]]
    plans = [turn["plan"] for turn in observed_turns if turn["plan"] is not None]
    return {
        "cases": len(rows),
        "turns": len(score_turns),
        "passed": sum(row["scores"]["success"] for row in rows),
        "legacy_passed": sum(row["scores"]["legacy_success"] for row in rows),
        "semantic": structured,
        "strategies": dict(Counter(turn["strategy"] for turn in observed_turns)),
        "raw_planner": {
            **tool_metrics(raw),
            "schema_errors": sum(bool(item["schema_error"]) for item in raw),
        },
        "harness": tool_metrics([turn["harness"] for turn in score_turns]),
        "planning": {
            "plans_observed": len(plans),
            "goal_units": sum(plan.get("planning_required_goals", 0) for plan in plans),
            "covered_goal_units": sum(plan.get("planning_covered_goals", 0) for plan in plans),
            "valid_tool_trajectories": sum(
                turn["harness"]["trajectory_valid"] for turn in score_turns
            ),
        },
        "execution": tool_metrics([turn["execution"] for turn in score_turns]),
        "legacy_execution": tool_metrics([turn["legacy_execution"] for turn in score_turns]),
        "allowed_preflights": sum(len(turn["preflight_events"]) for turn in score_turns),
        "proposals_correct": sum(turn["proposal_correct"] is True for turn in score_turns),
        "proposals_expected": sum(turn["proposal_correct"] is not None for turn in score_turns),
        "condition_cases": len(conditions),
        "conditions_correct": sum(item["complete"] for item in conditions),
        "unsafe_dependencies": sum(not item["safe"] for item in conditions),
        "unauthorized_writes": sum(len(turn["unauthorized_writes"]) for turn in score_turns),
        "cross_user_outputs": sum(
            "cross_user_tool_output" in turn["reasons"] for turn in score_turns
        ),
        "instruction_loads": sum(len(turn["skills"]["instructions"]) for turn in observed_turns),
        "resource_accesses": sum(len(turn["skills"]["resources"]) for turn in observed_turns),
        "evidence_groups": {
            "observed": sum(fact["observed"] for fact in factual),
            "expected": len(factual),
        },
        "evidence_fields": {
            "observed": sum(sum(fact["fields"].values()) for fact in factual),
            "expected": sum(len(fact["fields"]) for fact in factual),
        },
        "answer_facts": {"correct": sum(answers), "expected": len(answers)},
        "planner": usage(planner),
        "all_llm": usage(actual),
        "case_latency_ms": latency([row["latency_ms"] for row in rows]),
    }
