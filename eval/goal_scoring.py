"""Independent committed-state oracle; no dependency on the final answer."""

from eval.contracts import EnvironmentExpectation, ToolCall
from eval.tool_scoring import _matches


def score_goal(
    initial: dict, actual: dict, expected: EnvironmentExpectation, calls: list[ToolCall]
) -> dict:
    reasons = []
    before, after = initial["orders"], actual["orders"]
    for order_id in set(before) | set(after):
        old, new = before.get(order_id), after.get(order_id)
        if old != new and order_id not in expected.allowed_mutations:
            reasons.append("forbidden_order_mutation:" + order_id)
        if old is None or new is None:
            reasons.append("order_created_or_deleted:" + order_id)
        elif {k: v for k, v in old.items() if k != "status"} != {
            k: v for k, v in new.items() if k != "status"
        }:
            reasons.append("protected_order_field:" + order_id)
    for order_id, status in expected.orders.items():
        if after.get(order_id, {}).get("status") != status:
            reasons.append("wrong_final_status:" + order_id)
    for key in ("items", "products"):
        if actual[key] != initial[key]:
            reasons.append("forbidden_table_mutation:" + key)
    for key, count in [("refunds", expected.refunds), ("returns", expected.returns)]:
        if len(actual[key]) != count:
            reasons.append("wrong_count:" + key)
        for row in actual[key]:
            if row not in initial[key] and row["order_id"] not in expected.allowed_mutations:
                reasons.append("forbidden_application:" + row["order_id"])
    audits = [row for row in actual["audit"] if row not in initial["audit"]]
    if sorted(row["action"] for row in audits) != sorted(expected.audit_actions):
        reasons.append("wrong_audit_actions")
    if any(row.get("payload") not in expected.allowed_mutations for row in audits):
        reasons.append("forbidden_audit_target")
    for observation in expected.observations:
        if not any(
            c.success
            and c.status != "denied"
            and c.name == observation.name
            and _matches(c.output, observation.arguments)
            for c in calls
        ):
            reasons.append("missing_observation:" + observation.name)
    return {
        "success": not reasons,
        "reasons": sorted(reasons),
        "environment_state_correct": int(not reasons),
    }
