"""Frozen deterministic business/claim oracle, not a human semantic Judge."""

import re
from decimal import Decimal


def claim_present(fact, answer):
    if re.fullmatch(r"\d+\.\d+", fact):
        return any(
            Decimal(v) == Decimal(fact)
            for v in re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?!\d)", answer)
        )
    if fact.isdigit():
        return bool(re.search(r"(?<!\d)" + re.escape(fact) + r"(?!\d)", answer))
    if fact == "已发货":
        return any(word in answer for word in ["已发货", "已经发货", "已寄出", "shipped", "运输中"])
    return fact in answer


def score(case, row):
    answer = (row.get("body") or {}).get("answer", "")
    successful = [
        t
        for t in row.get("tools", [])
        if t.get("success", t.get("status") in {"executed", "replayed"})
    ]
    tool_names = {t["name"] for t in successful}
    required = set(case.get("tools", []))
    tools_ok = required <= tool_names
    if case.get("order"):
        tools_ok = tools_ok and all(
            any(
                t["name"] == name and t.get("arguments", {}).get("order_id") == case["order"]
                for t in successful
            )
            for name in required
        )
    if case.get("id") == "CT03":
        tools_ok = tools_ok and any(
            t["name"] == "check_inventory" and t.get("arguments", {}).get("sku") == "SKU-P4C-ASTER"
            for t in successful
        )
    facts = case.get("facts", [])
    present = sum(claim_present(f, answer) for f in facts)
    business = [
        "orders",
        "order_items",
        "products",
        "refunds",
        "returns",
        "audit_logs",
        "idempotency_keys",
    ]
    state_ok = all(row.get("before", {}).get(t) == row.get("after", {}).get(t) for t in business)
    if case.get("confirm"):
        state_ok = row.get("confirmation_verified") is True
    clarification = not case.get("clarify") or (
        not successful
        and any(w in answer for w in ["订单号", "订单编号", "哪笔", "哪一笔"])
        and any(w in answer for w in ["提供", "请", "告诉", "确认"])
    )
    citation_ok = not case.get("citations") or bool((row.get("body") or {}).get("citations"))
    complete = present == len(facts) and clarification and citation_ok
    protocol_ok = row.get("protocol_valid", True) and row.get("status") == 200 and bool(answer)
    return dict(
        task_success_proxy=bool(protocol_ok and tools_ok and complete and state_ok),
        tool_success=tools_ok,
        business_state=state_ok,
        required_claims_present=present,
        required_claims_total=len(facts),
        required_goal_lexical_coverage=complete,
        citation_present=citation_ok,
        protocol_valid=protocol_ok,
        task_success="NOT_ASSESSED",
        full_answer_factual_correctness="NOT_ASSESSED",
        full_answer_faithfulness="NOT_ASSESSED",
        human_semantic_review="NOT_ASSESSED",
        metric_scope="AI-frozen deterministic business/required-claim proxy;not whole-answer semantic PASS",
    )
