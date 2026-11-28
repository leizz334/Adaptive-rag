"""Ground the bounded payment workflow in the current utterance and its task scope."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.memory.context import ORDER_PATTERN, user_orders
from app.schemas.goals import GOAL_FIELDS, DependencyHint, GoalKind, TaskGoal, VerifiedDependency

_SENTENCE = re.compile(r"[。；;！？!?\n]+")
_CONDITIONAL = re.compile(r"^(?:如果|假如|要是|若|只有在|只有|只在|只要|等到|等)")
_PAYMENT = re.compile(
    r"(?:已(?:经)?)?(?:付款|支付)(?:(?:已(?:经)?)?(?:成功|完成)|了|过)?|已付(?:款|清)?|付(?:了|过)"
    r"|(?:有|能查到|查到)(?:实际)?(?:付款|支付)(?:记录|时间)"
)
_VERIFY = re.compile(r"^(?:请|麻烦|得|需要)?\s*先(?:帮我)?(?:确认|核对|查(?:明|一下)?)")
_TRANSITION = re.compile(r"^(?:另外|同时|顺便|接下来|还有)\s*")
_LINK = re.compile(r"(?:的话|之后|以后|后)?\s*(?:才|再)(?:帮我|给我|能)?(?=查|看|列|核对)")
_DENY = re.compile(r"不要|不用|不必|无需|别|不想|不能|未付|没付|或者|或是|除非")
_WRONG_ORDER = re.compile(
    r"(?:另(?:一|个)|另外一|其他|其它|之前(?:的|那|一)|上一|刚才(?:的|那)).{0,6}(?:订单|单|笔)"
)
_REQUEST_VERB = re.compile(r"查|看|列|核对|告诉")
_PAYMENT_REPORT = re.compile(
    r"(?:未|没(?:有)?)付(?:款)?(?:的话|时)\s*只(?:说明|报告|显示)(?:订单)?(?:付款|支付)状态"
)
_TRUSTED = {"current_user", "session_user", "session_summary_user_entity"}


def has_partial_order_token(text: str) -> bool:
    return any(
        text[match.start() - 1 : match.start()] == "-" or text[match.end() : match.end() + 1] == "-"
        for match in ORDER_PATTERN.finditer(text)
    )


def _payment_text(text: str) -> str:
    value = ORDER_PATTERN.sub("", text).strip()
    value = _TRANSITION.sub("", value).strip()
    value = re.sub(r"^(?:(?:这|那)(?:张|笔)?(?:订单|单|笔)|该订单)\s*", "", value)
    value = _CONDITIONAL.sub("", value).strip()
    return re.sub(r"^(?:这(?:笔|单)|该)?(?:订单)?\s*", "", value).strip()


def _is_affirmative_payment(text: str) -> bool:
    value = _VERIFY.sub("", _payment_text(text)).strip()
    value = re.sub(r"^(?:确认|确定)\s*", "", value)
    value = re.sub(r"(?:的时候|的话|以后|之后|时|后)$", "", value).strip()
    return _PAYMENT.fullmatch(value) is not None


def _is_payment_check(text: str) -> bool:
    # An inquiry can supply the order for the check. It cannot supply the predicate.
    value = _payment_text(text)
    check = _VERIFY.match(value)
    if not check:
        return False
    value = value[check.end() :].strip()
    value = re.sub(r"^是否\s*|^有没(?=有)", "", value)
    return _PAYMENT.fullmatch(value) is not None


def _relations(text: str) -> list[tuple[str, str, str, tuple[int, ...]]]:
    """Find supported condition and dependent spans without inferring an entity."""
    sentences = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    matches: list[tuple[str, str, str, tuple[int, ...]]] = []
    preceding = None
    for index, sentence in enumerate(sentences):
        clauses = [part.strip() for part in re.split("[，,]", sentence) if part.strip()]
        for ordinal, clause in enumerate(clauses):
            previous = clauses[ordinal - 1] if ordinal else None
            if previous and _CONDITIONAL.match(previous) and _is_affirmative_payment(previous):
                matches.append((previous, previous, clause, (index,)))
            elif link := _LINK.search(clause):
                prefix = clause[: link.start()].strip()
                if _is_affirmative_payment(prefix):
                    anchor = previous or preceding
                    if anchor and (_is_affirmative_payment(anchor) or _is_payment_check(anchor)):
                        scope = (index,) if previous else (index - 1, index)
                        matches.append((anchor, prefix, clause, scope))
                    else:
                        # A separate preceding non-payment task cannot supply an order ID.
                        matches.append((prefix, prefix, clause, (index,)))
                elif not prefix and previous and _is_affirmative_payment(previous):
                    matches.append((previous, previous, clause, (index,)))
        preceding = clauses[-1] if clauses else None
    return matches


def bind_payment_dependency(
    text: str, goals: Sequence[TaskGoal], hints: Sequence[DependencyHint] = ()
) -> list[TaskGoal]:
    original = list(goals)
    relations = _relations(text)
    if not relations:
        return original
    predicates = tuple(relation[1] for relation in relations)
    blocked = [
        goal.model_copy(
            update={"conditions": tuple(dict.fromkeys((*goal.conditions, *predicates)))}
        )
        for goal in goals
    ]
    active = [goal for goal in goals if not goal.negated]
    if (
        len(relations) != 1
        or not active
        or any(goal.operation == "write" for goal in active)
        or has_partial_order_token(text)
    ):
        return blocked
    anchor, condition, action, scope = relations[0]
    if _DENY.search(action) or _WRONG_ORDER.search(action) or not _REQUEST_VERB.search(action):
        return blocked
    # Hints may identify equivalent substrings. Never let a model substitute the source span.
    grounded = [
        hint
        for hint in hints
        if text.count(hint.condition_quote) == text.count(hint.action_quote) == 1
        and hint.condition_quote != hint.action_quote
        and hint.condition_quote in condition
        and hint.action_quote in action
    ]
    terminal = grounded[0].action_quote if len(grounded) == 1 else action
    candidates = [
        goal for goal in active if goal.kind == GoalKind.ORDER_ITEMS and goal.request_text in action
    ]
    if len(candidates) != 1:
        return blocked
    dependent = candidates[0]
    identifiers = set(user_orders(anchor)) | set(user_orders(action))
    if (
        len(identifiers) > 1
        or dependent.unavailable_fields
        or any(dep not in anchor and dep not in action for dep in dependent.conditions)
    ):
        return blocked
    selected = next(
        iter(identifiers), dependent.entity_id if dependent.entity_source in _TRUSTED else None
    )
    if not selected or (dependent.entity_id and dependent.entity_id != selected):
        return blocked
    source = "current_user" if identifiers else dependent.entity_source
    proof = VerifiedDependency(
        condition_quote=condition, action_quote=terminal, prerequisite_order_id=selected
    )
    sentences = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    result = []
    for goal in goals:
        if goal is dependent:
            result.append(
                goal.model_copy(
                    update={
                        "entity_id": selected,
                        "entity_source": source,
                        "entity_scope": "local" if identifiers else goal.entity_scope,
                        "conditions": (condition,),
                        "clarification": (),
                        "verified_dependency": proof,
                    }
                )
            )
        elif (
            goal.kind in {GoalKind.ORDER_PAYMENT, GoalKind.UNKNOWN}
            and goal.entity_id in {None, selected}
            and (
                goal.request_text in anchor
                or _PAYMENT_REPORT.fullmatch(goal.request_text)
                or (goal.kind == GoalKind.ORDER_PAYMENT and goal.request_text in action)
            )
            and not any(dep not in anchor and dep not in action for dep in goal.conditions)
        ):
            reports_payment = any(_PAYMENT_REPORT.fullmatch(sentence) for sentence in sentences)
            if (
                goal.request_text in action
                and goal.request_text not in anchor
                and not reports_payment
            ):
                # The payment mention is the workflow's prerequisite, not a separate read.
                continue
            if goal.kind == GoalKind.ORDER_PAYMENT or re.search(r"确认|核对|查", anchor):
                result.append(
                    goal.model_copy(
                        update={
                            "kind": GoalKind.ORDER_PAYMENT,
                            "entity_type": "order",
                            "entity_id": selected,
                            "entity_source": source,
                            "entity_scope": "local" if identifiers else dependent.entity_scope,
                            "fields": GOAL_FIELDS[GoalKind.ORDER_PAYMENT],
                            "conditions": (),
                            "operation": "read",
                            "clarification": (),
                            "independent": True,
                        }
                    )
                )
        elif (
            goal.entity_id
            and goal.entity_source == "current_user"
            and goal.entity_scope in {"local", "distributive"}
            and goal.operation == "read"
            and not goal.negated
            and any(
                goal.request_text in sentence
                for index, sentence in enumerate(sentences)
                if index not in scope
            )
            and not any(dep not in anchor and dep not in action for dep in goal.conditions)
        ):
            result.append(goal.model_copy(update={"conditions": (), "independent": True}))
        else:
            result.append(goal)
    return result
