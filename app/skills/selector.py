"""Validate semantic skill hints against grounded goals and supported operations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.agents.dependencies import has_partial_order_token
from app.agents.goals import SKU_RE
from app.memory.context import user_orders
from app.observability.tracing import span
from app.schemas.goals import GoalKind, SkillHint, TaskGoal
from app.skills.registry import SkillRegistry
from app.skills.schemas import SkillMetadata

SkillRuntimeMode = Literal["instructions", "workflows", "conditional"]
Clarification = Literal["order_id", "return_reason", "return_scope"]
_BLOCKED = {"out_of_scope", "human_handoff", "complaint", "greeting", "chitchat"}
_SOURCES = {"current_user", "session_user", "session_summary_user_entity"}
_QUOTED = re.compile(r'「[^」]*」|『[^』]*』|“[^”]*”|"[^"]*"')
_ITEM_SCOPE = re.compile(
    r"只(?:想|要)?退|部分退货|单件退货|其中.{0,16}(?:退|商品|一[件个款])"
    r"|(?:这|那|某|单独一)[件款][^，。；;]{0,20}(?:退|商品)"
    r"|ORD\d+\s*(?:(?:里|中)面?)?的\s*(?!退货(?:申请)?(?:[\s，。；;？！!?]|$))[^，。；;？！!?]",
    re.IGNORECASE,
)
_REASON = re.compile(r"(?:退货)?原因(?:就)?(?:为|是|写|填|[:：])\s*([^，,。；;！？!?\n]{1,200})")
_NON_ACTION = re.compile(
    r"是否|是不是|有没有|能不能|可不可以|能否|可以吗|规则|规定|政策|办理流程|怎么办|怎么退"
    r"|(?:取消|退货)(?:状态|记录|进度)|(?:如果|假如|要是|除非|只要|前提)"
)
_DENIAL = re.compile(
    r"(?:不要|不用|不必|无需|别|并非|不是要|不是想|不想)"
    r"\s*(?:(?:再|先|现在|帮我|替我|给我|真的|直接)\s*){0,4}"
    r"(?:取消|撤销|撤掉|退货|退款|申请|办理|提交|操作|查|查询|看|列出|打开|给|显示|发给)"
)
_REQUEST_REASON = re.compile(r"^(?:请|麻烦|帮我|尽快|希望|可以|尽量|有空|我想)")


@dataclass(frozen=True)
class SkillSelection:
    name: str | None = None
    reason_code: str = "no_match"
    order_id: str | None = None
    reason: str | None = None
    clarification: Clarification | None = None
    conditional_goal: TaskGoal | None = None
    independent_goals: tuple[TaskGoal, ...] = ()
    use_workflow: bool = False
    use_reference: bool = False
    open_catalog: bool = False
    relevant: tuple[str, ...] = ()
    eligible: tuple[str, ...] = ()

    @property
    def requires_agent(self) -> bool:
        return self.use_workflow or self.open_catalog or self.clarification is not None


def skill_discovery_prompt(catalog: Sequence[SkillMetadata]) -> str:
    if not catalog:
        return ""
    items = "\n".join(f"- {item.name}: {item.description}" for item in catalog)
    return (
        "\n\n可用技能目录，仅用于候选识别：\n"
        f"{items}\n"
        "在原 JSON 中可附 skill_hints 数组，最多四项。每项给 name 和本轮原文 quote。"
        "只判断技能与本轮话题相关性。咨询、已有状态和写操作是不同目标，候选不代表执行许可。"
        "若退货原因已经在本轮说明，可附原文 reason_quote。"
        "若用户在商品推荐中明确需要筛选依据或比较口径，可附 needs_reference:true。"
        "附加字段不能改变现有意图标签或 goal_signals 的定义。"
    )


def _source_text(query: str) -> str:
    return _QUOTED.sub(lambda match: " " * len(match[0]), query)


def _grounded(fragment: str, text: str) -> bool:
    return bool(fragment.strip()) and text.count(fragment) == 1


def affirmative_action(query: str, goal: TaskGoal) -> bool:
    """Eligibility/status questions, denials and partial identifiers cannot authorize a write."""
    text = _source_text(query)
    if (
        goal.negated
        or goal.conditions
        or not _grounded(goal.request_text, text)
        or has_partial_order_token(text)
    ):
        return False
    sentences = re.split(r"([。；;！？!?\n])", text)
    return not _DENIAL.search(text) and any(
        goal.request_text in sentence
        and not _NON_ACTION.search(sentence)
        and following not in {"？", "?"}
        for sentence, following in zip(sentences[::2], [*sentences[1::2], ""], strict=True)
    )


def requests_item_return(text: str) -> bool:
    return bool(_ITEM_SCOPE.search(text) or (SKU_RE.search(text) and "整单" not in text))


def _trusted(goal: TaskGoal) -> bool:
    return bool(goal.entity_id and goal.entity_source in _SOURCES and not goal.clarification)


def _return_reason(text: str, hint: SkillHint | None) -> str | None:
    explicit = _REASON.search(text)
    candidate = explicit[1] if explicit else hint.reason_quote if hint else None
    if candidate:
        reason = candidate.strip()
        if (
            _grounded(reason, text)
            and not user_orders(reason)
            and not _REQUEST_REASON.search(reason)
            and not any(term in reason for term in ("没说", "还没", "待补", "申请退货", "提交退货"))
        ):
            return reason
    return None


def _approve_selection(
    item: SkillMetadata, text: str, goals: Sequence[TaskGoal], hint: SkillHint | None
) -> SkillSelection | None:
    writes = [goal for goal in goals if goal.operation == "write"]
    if len(writes) != 1 or writes[0].kind not in item.goals:
        return None
    goal = writes[0]
    if not affirmative_action(text, goal):
        return None
    # A separate unresolved requested action or another evidence goal can require Dynamic.
    if any(other.kind != GoalKind.UNKNOWN and other is not goal for other in goals):
        return None
    if not _trusted(goal):
        return SkillSelection(item.name, "needs_clarification", clarification="order_id")
    reason = None
    if goal.kind == GoalKind.RETURN_REQUEST:
        if requests_item_return(text):
            return SkillSelection(item.name, "needs_clarification", clarification="return_scope")
        reason = _return_reason(text, hint)
        if reason is None:
            return SkillSelection(item.name, "needs_clarification", clarification="return_reason")
    return SkillSelection(
        item.name, "grounded_action", order_id=goal.entity_id, reason=reason, use_workflow=True
    )


def _conditional_selection(item: SkillMetadata, goals: Sequence[TaskGoal]) -> SkillSelection | None:
    eligible = [goal for goal in goals if goal.verified_dependency and goal.kind in item.goals]
    if len(eligible) != 1:
        return None
    goal = eligible[0]
    proof = goal.verified_dependency
    assert proof is not None
    independent = tuple(other for other in goals if other is not goal)
    if any(
        other.operation != "read"
        or not other.independent
        or other.conditions
        or not _trusted(other)
        or other.unavailable_fields
        for other in independent
    ):
        return None
    return SkillSelection(
        item.name,
        "grounded_dependency",
        order_id=proof.prerequisite_order_id,
        conditional_goal=goal,
        independent_goals=independent,
        use_workflow=True,
    )


def select_skill(
    registry: SkillRegistry,
    query: str,
    intent: str,
    goals: Sequence[TaskGoal],
    hints: Sequence[SkillHint] = (),
    *,
    mode: SkillRuntimeMode,
) -> SkillSelection:
    text = _source_text(query)
    active = [goal for goal in goals if not goal.negated]
    grounded = {hint.name: hint for hint in hints if _grounded(hint.quote, text)}
    catalog = registry.metadata()
    kinds = {goal.kind for goal in active}
    relevant = set(grounded).intersection(item.name for item in catalog)
    ranked = []
    if intent not in _BLOCKED:
        for item in catalog:
            hint = grounded.get(item.name)
            activation = item.extensions.get("adaptive-activation")
            if activation == "catalog" and not hint:
                # A quoted product title is data in a grounded, read-only catalog request.
                hint = next(
                    (
                        value
                        for value in hints
                        if value.name == item.name
                        and _grounded(value.quote, query)
                        and _source_text(value.quote).strip()
                    ),
                    None,
                )
            if hint or kinds.intersection(item.goals):
                relevant.add(item.name)
            if activation == "action":
                candidate = _approve_selection(item, text, active, hint)
                if candidate:
                    if mode == "instructions":
                        candidate = SkillSelection(item.name, "grounded_action")
                    ranked.append((3, candidate))
            elif activation == "condition":
                if mode == "conditional" and (candidate := _conditional_selection(item, active)):
                    ranked.append((3, candidate))
            elif compatibility := _instruction_rank(item, intent, active, hint):
                open_catalog = bool(
                    activation == "catalog"
                    and (hint or intent == "recommendation")
                    and intent in item.intents
                    and not user_orders(text)
                    and not SKU_RE.search(text)
                    and not any(goal.entity_id or goal.conditions for goal in active)
                )
                ranked.append(
                    (
                        compatibility,
                        SkillSelection(
                            item.name,
                            "model_candidate" if hint else "grounded_goal",
                            use_reference=bool(hint and hint.needs_reference and item.resources),
                            open_catalog=open_catalog,
                        ),
                    )
                )
    best_rank = max((rank for rank, _ in ranked), default=0)
    best = [candidate for rank, candidate in ranked if rank == best_rank]
    selected = (
        best[0]
        if len(best) == 1
        else SkillSelection(reason_code="conflict" if best else "no_match")
    )
    selected = replace(
        selected,
        relevant=tuple(sorted(relevant)),
        eligible=tuple(
            sorted(
                {
                    candidate.name
                    for _, candidate in ranked
                    if candidate.name and not candidate.clarification
                }
            )
        ),
    )
    with span(
        "skill.selection",
        skill_candidates=selected.relevant,
        skill_eligible=selected.eligible,
        skill_name=selected.name,
        skill_selection_reason=selected.reason_code,
    ):
        pass
    return selected


def _instruction_rank(
    item: SkillMetadata, intent: str, active: Sequence[TaskGoal], hint: SkillHint | None
) -> int:
    if any(goal.operation == "write" or goal.conditions for goal in active):
        return 0
    kinds = {goal.kind for goal in active if goal.kind != GoalKind.UNKNOWN}
    if kinds and not kinds.issubset(item.goals):
        return 0
    if hint and (intent in item.intents or kinds):
        return 2
    if not kinds and intent == "recommendation" and intent in item.intents:
        return 1
    return int(bool(kinds and intent in item.intents))
