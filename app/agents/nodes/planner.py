"""Planner that turns intent, skills and complexity into tool plans."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.agents.state import AgentState
from app.core.exceptions import LLMOutputError, LLMProviderError
from app.core.ids import new_id
from app.memory.context import node_context, node_query
from app.observability.tracing import traced
from app.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from app.providers.base import LLMProvider
from app.providers.fake import OfflineLLMProvider
from app.providers.json_parser import parse_model
from app.schemas.agent import AgentPlan, PlanStep
from app.schemas.chat import ActionProposal
from app.skills.loader import match_skill
from app.tools.permissions import WRITE_RISKS
from app.tools.registry import ToolRegistry

_ORDER_RE = re.compile(r"(?<![A-Za-z0-9_])ORD\d+(?![A-Za-z0-9_])", re.IGNORECASE)
_ALWAYS_AVAILABLE = ("search_knowledge", "escalate_to_human")
_ORDER_TOOLS = {
    "get_order",
    "get_order_items",
    "track_shipment",
    "cancel_order",
    "create_return_request",
    "create_refund_request",
}


class Planner:
    def __init__(self, llm: LLMProvider, registry: ToolRegistry) -> None:
        self._llm = llm
        self._registry = registry

    def _tool_catalog(self, allowed: set[str] | None = None) -> str:
        lines = []
        for tool in self._registry.all():
            if allowed is not None and tool.name not in allowed:
                continue
            schema = json.dumps(tool.input_model.model_json_schema(), ensure_ascii=False)
            lines.append(
                f"- {tool.name}: {tool.description} [{tool.risk.value}] arguments={schema}"
            )
        return "\n".join(lines) or "- (no tools)"

    async def create_plan(
        self,
        query: str,
        intent_label: str,
        summary: str,
        *,
        raw_query: str | None = None,
        order_ids: tuple[str, ...] = (),
    ) -> AgentPlan:
        raw = raw_query if raw_query is not None else query.partition("（会话指代：")[0]
        targets = _order_ids(raw) or order_ids or _order_ids(query)
        # Ground references without changing which evidence the raw user requested.
        if targets and not _order_ids(query):
            query += "（会话指代：订单 " + ", ".join(targets) + "）"
        skill = match_skill(raw, intent_label)
        allowed = _allowed_tools(skill, self._registry, raw)
        if isinstance(self._llm, OfflineLLMProvider):
            return (
                skill_to_plan(skill, query, self._registry, raw_query=raw, order_ids=targets)
                if skill
                else _knowledge_fallback(query, self._registry)
            )
        try:
            response = await self._llm.generate(
                [
                    {
                        "role": "system",
                        "content": PLANNER_SYSTEM.format(
                            tools=self._tool_catalog(allowed),
                            skill_context=_format_skill(skill),
                        ),
                    },
                    {
                        "role": "user",
                        "content": PLANNER_USER.format(
                            query=query,
                            intent=intent_label,
                            summary=summary or "无",
                            raw_query=raw,
                            order_ids=json.dumps(targets),
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            plan = parse_model(response.content, AgentPlan)
            plan = _sanitize_plan(plan, self._registry, allowed, order_ids=targets)
            if plan.rationale == "clarification_required":
                return plan
            if plan.steps:
                if skill:
                    plan.rationale = f"skill:{skill['name']};{plan.rationale}"
                return plan
        except (LLMOutputError, LLMProviderError):
            pass
        if skill:
            return skill_to_plan(skill, query, self._registry, raw_query=raw, order_ids=targets)
        return _knowledge_fallback(query, self._registry)


def _skill_tools(skill: dict, query: str) -> list[str]:
    tools = list(skill.get("tools", []))
    if skill.get("name") == "order_tracking":
        tools = _evidence_tools(query) or tools
    return tools


def _evidence_tools(query: str) -> list[str]:
    """Small evidence capabilities, independent of utterance shape or entity ID."""
    raw = query.partition("（会话指代：")[0]
    shipment = any(
        cue in raw for cue in ("物流", "快递", "轨迹", "运单", "运输", "配送", "到哪", "节点")
    )
    # A shipment's 状态 is not also a request for the order header.
    header_text = re.sub(r"(?:物流|快递|运输|配送)(?:的)?状态", "", raw)
    header = any(cue in header_text for cue in ("状态", "金额", "支付", "付款")) or bool(
        re.search(r"(?:是否|有没有)(?:已经|已)?发货", header_text)
    )
    items = any(cue in raw for cue in ("商品明细", "订单明细", "买了什么", "数量", "定制"))
    return (
        (["get_order"] if header else [])
        + (["track_shipment"] if shipment else [])
        + (["get_order_items"] if items else [])
    )


def _order_ids(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.upper() for value in _ORDER_RE.findall(query)))


def _allowed_tools(skill: dict | None, registry: ToolRegistry, query: str = "") -> set[str] | None:
    if skill is None:
        return None
    names = set(registry.names())
    tools = _skill_tools(skill, query)
    if skill.get("name") == "order_tracking":
        # Capability keywords cannot establish that an additional, unfamiliar
        # obligation is absent. Keep candidates unless every query token is
        # accounted for by the small order-header contract below.
        tools = list(dict.fromkeys([*skill.get("tools", []), *tools]))
        remainder = _ORDER_RE.sub("", query)
        remainder = re.sub(r"订单|的|支付|付款|状态|金额|[\s?？!！。,.，]", "", remainder)
        if not remainder and _evidence_tools(query) == ["get_order"]:
            tools = ["get_order"]
    allowed = {name for name in tools if name in names}
    allowed.update(name for name in _ALWAYS_AVAILABLE if name in names)
    return allowed or None


def _format_skill(skill: dict | None) -> str:
    if skill is None:
        return "无（通用工具集）"
    steps = "、".join(skill.get("steps") or [])
    tools = ", ".join(skill.get("tools") or [])
    return f"{skill['name']}：{skill.get('description', '')}。步骤：{steps}。工具：{tools}"


def _sanitize_plan(
    plan: AgentPlan,
    registry: ToolRegistry,
    allowed: set[str] | None,
    *,
    order_ids: tuple[str, ...] = (),
) -> AgentPlan:
    names = set(registry.names())
    if allowed is not None:
        names = names & allowed
    steps = []
    for step in plan.steps:
        if not step.tool_name:
            steps.append(step)
            continue
        if step.tool_name not in names:
            continue
        tool = registry.get(step.tool_name)
        if "order_id" in tool.input_model.model_fields:
            if not order_ids:
                return AgentPlan(steps=[], rationale="clarification_required")
            if step.arguments.get("order_id") not in order_ids:
                continue
        try:
            arguments = tool.input_model.model_validate(step.arguments).model_dump(mode="json")
        except ValidationError:
            continue
        # Only execution can establish whether an observation succeeded. Keep
        # bounded repeated steps so a transient failure can still be repaired.
        steps.append(step.model_copy(update={"arguments": arguments}))
    return AgentPlan(steps=steps[:6], rationale=plan.rationale)


def skill_to_plan(
    skill: dict,
    query: str,
    registry: ToolRegistry,
    *,
    raw_query: str | None = None,
    order_ids: tuple[str, ...] = (),
) -> AgentPlan:
    steps: list[PlanStep] = []
    raw = raw_query if raw_query is not None else query.partition("（会话指代：")[0]
    targets = _order_ids(raw) or order_ids or _order_ids(query)
    for tool_name in _skill_tools(skill, raw):
        if tool_name not in registry.names():
            continue
        if tool_name in _ORDER_TOOLS and not targets:
            return AgentPlan(steps=[], rationale="clarification_required")
        for target in targets if tool_name in _ORDER_TOOLS else (None,):
            arguments = _tool_arguments(tool_name, raw)
            if target:
                arguments["order_id"] = target
            steps.append(
                PlanStep(
                    step_id=len(steps) + 1,
                    goal=skill["name"],
                    tool_name=tool_name,
                    arguments=arguments,
                    needs_retrieval=tool_name == "search_knowledge",
                )
            )
    if steps:
        plan = AgentPlan(steps=steps[:6], rationale=f"skill:{skill['name']}")
        # The offline scripted fixture has a names-only Catalog; real registries
        # additionally validate concrete tool contracts before any dispatch.
        return (
            _sanitize_plan(plan, registry, None, order_ids=targets)
            if hasattr(registry, "get")
            else plan
        )
    return _knowledge_fallback(query, registry)


def _tool_arguments(tool_name: str, query: str) -> dict:
    if tool_name in {"search_knowledge"}:
        return {"query": query[:200]}
    if tool_name in {"search_products"}:
        return {"query": query[:80]}
    if tool_name == "recommend_products":
        return {"query": query[:80]}
    if tool_name in {
        "get_order",
        "get_order_items",
        "track_shipment",
        "cancel_order",
        "create_return_request",
        "create_refund_request",
    }:
        match = _ORDER_RE.search(query)
        if match:
            arguments = {"order_id": match.group(0).upper()}
            if tool_name in {"create_return_request", "create_refund_request"}:
                arguments["reason"] = query[:200]
            return arguments
    return {}


def _knowledge_fallback(query: str, registry: ToolRegistry) -> AgentPlan:
    if "search_knowledge" in registry.names():
        return AgentPlan(
            steps=[
                PlanStep(
                    step_id=1,
                    goal="policy lookup",
                    tool_name="search_knowledge",
                    arguments={"query": query},
                    needs_retrieval=True,
                )
            ],
            rationale="fallback_knowledge",
        )
    return AgentPlan(steps=[], rationale="empty")


@traced("node.planner", "chain")
async def planner_node(state: AgentState, planner: Planner) -> dict:
    confirmed = state.get("confirmed_action")
    if confirmed is not None:
        return {
            "plan": AgentPlan(
                steps=[
                    PlanStep(
                        step_id=1,
                        goal="confirmed action",
                        tool_name=confirmed.tool_name,
                        arguments=confirmed.arguments,
                    )
                ],
                rationale="confirmed_action",
            ),
            "pending_action": None,
        }
    intent = state.get("intent")
    context = state.get("selected_context")
    plan = await planner.create_plan(
        node_query(state),
        intent.label.value if intent else "faq_policy",
        node_context(state, "planner")
        if state.get("memory_managed")
        else state.get("summary") or "",
        raw_query=state["user_query"],
        order_ids=getattr(context, "order_ids", ())
        or ((context.order_id,) if context and context.order_id else ()),
    )
    if plan.rationale == "clarification_required":
        return {"plan": plan, "pending_action": None, "extra": {"missing_order_id": True}}
    write_steps = [
        step
        for step in plan.steps
        if step.tool_name and planner._registry.get(step.tool_name).risk in WRITE_RISKS
    ]
    if any(
        _explicit_write_request(state["user_query"], step.tool_name or "") for step in write_steps
    ):
        if any(not step.arguments.get("order_id") for step in write_steps):
            return {
                "plan": plan.model_copy(update={"steps": []}),
                "extra": {"missing_order_id": True},
            }
    plan = plan.model_copy(
        update={
            "steps": [
                step
                for step in plan.steps
                if step not in write_steps
                or _explicit_write_request(state["user_query"], step.tool_name or "")
            ]
        }
    )
    pending = None
    for step in plan.steps:
        if not step.tool_name:
            continue
        tool = planner._registry.get(step.tool_name)
        if tool.risk in WRITE_RISKS and not state.get("confirm_action_id"):
            pending = ActionProposal(
                action_id=new_id("act_"),
                tool_name=tool.name,
                arguments=step.arguments,
                risk=tool.risk,
                summary=_action_summary(tool.name, step.arguments),
            )
            break
    return {"plan": plan, "pending_action": pending}


def _explicit_write_request(query: str, tool_name: str) -> bool:
    if any(
        cue in query
        for cue in (
            "规则",
            "政策",
            "条件",
            "怎么",
            "能不能",
            "是否",
            "可以吗",
            "能退吗",
            "能取消吗",
        )
    ):
        return False
    if tool_name == "cancel_order":
        return any(cue in query for cue in ("取消", "不想要了"))
    if tool_name == "create_refund_request":
        return any(cue in query for cue in ("申请退款", "帮我退款", "我要退款"))
    if tool_name == "create_return_request":
        return any(cue in query for cue in ("申请退货", "帮我退货", "我要退货", "提交退货"))
    return False


def _action_summary(tool_name: str, arguments: dict) -> str:
    order_id = arguments.get("order_id", "该订单")
    if tool_name == "cancel_order":
        return f"确认后将取消订单 {order_id}。请核对订单号。"
    if tool_name == "create_refund_request":
        return f"确认后将为订单 {order_id} 提交退款申请；提交不代表退款已到账。"
    if tool_name == "create_return_request":
        return f"确认后将为订单 {order_id} 提交退货申请；提交不代表退款已到账。"
    return "确认后将提交该操作。"
