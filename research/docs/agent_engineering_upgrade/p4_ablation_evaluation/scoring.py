"""Bounded objective oracles. Open semantic truth is never inferred from a Judge."""

import re
from decimal import Decimal


def money_supported(answer, cents):
    expected = Decimal(cents) / 100
    matches = list(re.finditer(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?!\d)", answer))
    good = False
    for match in matches:
        if Decimal(match.group()) == expected:
            if re.search(
                r"不是|并非|不等于|非为", answer[max(0, match.start() - 5) : match.start()]
            ):
                return False
            good = True
    return good


def unchanged(before, after):
    names = [
        "orders",
        "order_items",
        "products",
        "refunds",
        "returns",
        "audit_logs",
        "idempotency_keys",
    ]
    return all(before.get(k) == after.get(k) for k in names)


def score(case, row):
    body = row.get("body") or {}
    answer = body.get("answer", "")
    tools = row.get("tools", [])
    fresh = any(
        t.get("success")
        and t["name"] == "get_order"
        and t.get("arguments", {}).get("order_id") == case.get("order")
        for t in tools
    )
    required = True
    citation = None
    facts = None
    if case["kind"] == "memory":
        required = money_supported(answer, case["cents"])
        facts = required
    elif case["kind"] == "rag":
        # Explicit bounded atoms: numerical duration, required conditions, exclusions.
        atoms = case["atoms"]
        checks = []
        for alternatives in atoms:
            checks.append(any(term in answer for term in alternatives))
        facts = all(checks) and not any(term in answer for term in case.get("forbidden", []))
        required = facts
        citation = bool(
            set(case["relevant_ids"]) & {c.get("document_id") for c in body.get("citations", [])}
        )
        fresh = citation
    state = unchanged(row["before"], row["after"])
    objective = bool(
        row.get("status") == 200
        and answer
        and fresh
        and required
        and state
        and row.get("protocol_valid", True)
    )
    return dict(
        objective_success=objective,
        tool_or_retrieval_evidence=fresh,
        business_state=state,
        required_bounded_facts=facts,
        required_goal_coverage=required,
        citation_matches_gold=citation,
        full_factual_correctness="NOT_ASSESSED",
        full_faithfulness="NOT_ASSESSED",
        human_semantics="NOT_ASSESSED",
        scope="bounded objective task oracle;not full semantic certification",
    )


def transitions(pairs, left, right):
    valid = [p for p in pairs if p.get("complete") and left in p["arms"] and right in p["arms"]]
    positive = sum(not p["arms"][left] and p["arms"][right] for p in valid)
    negative = sum(p["arms"][left] and not p["arms"][right] for p in valid)
    return dict(
        valid_pairs=len(valid),
        positive=positive,
        negative=negative,
        net=positive - negative,
        left_pass=sum(p["arms"][left] for p in valid),
        right_pass=sum(p["arms"][right] for p in valid),
    )
