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


def policy_verdict(case, answer):
    """Only bind explicitly supported field relationships; abstain on paraphrase gaps."""
    clauses = re.split(r"[。；;\n]", answer)
    if case.get("id") == "D_Q01":
        if re.search(r"(?:无需|不需要|不用).{0,8}(?:未使用|未通电|包装|配件|附件)", answer):
            return False
        excluded = False
        for clause in clauses:
            if re.search(r"(?:已烧水|烧过水|烧水后)", clause):
                denied = bool(
                    re.search(
                        r"(?:已烧水|烧过水|烧水后).{0,25}(?:不适用|不能|不可|无法|不支持|不接受).{0,15}(?:退货|退)",
                        clause,
                    )
                )
                if not denied and re.search(
                    r"(?:也|照样|仍然|同样|可以|可).{0,10}(?:退货|退)", clause
                ):
                    return False
                excluded = excluded or denied
        fields = [
            bool(re.search(r"14\s*天", answer)),
            bool(re.search(r"未(?:通电|使用)|没有(?:通电|使用)", answer)),
            bool(re.search(r"壶体无损|壶身无损|壶身完好|壶体完好|商品完好|壶体无破损", answer)),
            bool(re.search(r"包装.{0,12}(?:配件|附件).{0,8}(?:齐全|完整)", answer)),
            excluded,
        ]
    elif case.get("id") == "D_Q02":
        if re.search(r"(?:无需|不需要|不用).{0,8}订单(?:凭证|证明|记录)", answer):
            return False
        excluded = False
        for clause in clauses:
            if "进水" in clause:
                denied = bool(
                    re.search(
                        r"进水.{0,20}(?:不在|不包括|不包含|不涵盖|不适用|不属于|不予|不保修|不能免费|不免费|排除)",
                        clause,
                    )
                )
                if not denied and re.search(r"进水.{0,20}免费(?:维修|保修|修理)", clause):
                    return False
                excluded = excluded or denied
        fields = [
            bool(re.search(r"240\s*天", answer)),
            any(
                re.search(r"单侧|单边|一侧|一边", c)
                and re.search(r"无声|听不到|没声音", c)
                and re.search(r"免费(?:维修|修理)", c)
                for c in clauses
            ),
            bool(re.search(r"(?:需|须|提供|提交).{0,10}订单(?:凭证|证明|记录)", answer)),
            excluded,
        ]
    else:
        return True
    if any(
        re.search(r"(?:不是|并非|不等于)\s*" + n, answer)
        for n in re.findall(r"\d+", " ".join(t for group in case["atoms"] for t in group))
    ):
        return False
    return True if all(fields) else None


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
        negated_numeric = any(
            re.search(r"(?:不是|并非|不等于)\s*" + re.escape(number), answer)
            for alternatives in atoms
            for term in alternatives
            for number in re.findall(r"\d+", term)
        )
        facts = (
            all(checks)
            and not negated_numeric
            and not any(term in answer for term in case.get("forbidden", []))
        )
        relationship = policy_verdict(case, answer)
        if case.get("id") in {"D_Q01", "D_Q02"}:
            facts = (
                False
                if negated_numeric
                or any(term in answer for term in case.get("forbidden", []))
                or relationship is False
                else relationship
            )
        else:
            facts = False if facts is False or relationship is False else relationship
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
    if case["kind"] == "rag" and facts is None and row.get("status") == 200 and fresh and state:
        objective = None
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
    valid = [
        p
        for p in pairs
        if p.get("complete")
        and left in p["arms"]
        and right in p["arms"]
        and all(type(v) is bool for v in p["arms"].values())
    ]
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
