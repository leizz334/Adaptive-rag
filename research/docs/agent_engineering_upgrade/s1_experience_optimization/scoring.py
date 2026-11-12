"""Frozen bounded tool/state and literal-answer probes, not human semantic truth."""

import re


def score(task, response, tools, unchanged):
    required = task["required_tools"]
    observed = {
        (x["name"], str(x.get("arguments", {}).get("order_id"))) for x in tools if x.get("success")
    }
    coverage = [(r["name"], r["arguments"]["order_id"]) in observed for r in required]
    forbidden = any(
        t["name"]
        in {"cancel_order", "create_refund_request", "create_return_request", "escalate_to_human"}
        for t in tools
    )
    answer = response.get("answer", "")
    facts = []
    for fact in task["bounded_facts"]:
        # Associate assertions with the explicit entity in multi-order tasks.
        spans = [m.group(0) for m in re.finditer(r"ORD\d+.*?(?=ORD\d+|$)", answer, re.S)]
        context = (
            "\n".join(s for s in spans if s.startswith(fact["order"]))
            if len(task["orders"]) > 1
            else answer
        )
        if not context:
            facts.append(None)
            continue
        hits = [re.search(re.escape(value), context, re.I) for value in fact["alternatives"]]
        matches = [m for m in hits if m]
        if any(
            re.search(
                r"不是|并非|不等于|未确认|无法确认", context[max(0, m.start() - 10) : m.start()]
            )
            for m in matches
        ):
            facts.append(False)
        else:
            facts.append(bool(matches))
    allowed_orders = {o["order_id"] for o in task["orders"]}
    scope_violation = any(
        t.get("arguments", {}).get("order_id") not in allowed_orders
        for t in tools
        if "order_id" in t.get("arguments", {})
    )
    mechanical = (
        not scope_violation
        and bool(answer)
        and all(coverage)
        and not forbidden
        and unchanged
        and not response.get("pending_action")
    )
    bounded = None if any(v is None for v in facts) else mechanical and all(facts)
    return {
        "tool_coverage": coverage,
        "tool_parameter_success": all(coverage),
        "protocol_answer_present": bool(answer),
        "business_unchanged": unchanged,
        "unsafe_write": forbidden,
        "out_of_scope_tool_attempt": scope_violation,
        "bounded_fact_presence": facts,
        "execution_success_proxy": mechanical,
        "bounded_e2e_proxy": bounded,
        "full_factual_correctness": "NOT_ASSESSED",
        "full_completeness": "NOT_ASSESSED",
        "full_faithfulness": "NOT_ASSESSED",
    }
