"""Planner that turns intent, skills and complexity into tool plans."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from app.agents.action_proposals import action_summary
from app.agents.dynamic_planning import (
    DynamicPlanningMode,
    NativePlanningProvider,
    decode_native_plan,
    strict_tool_definitions,
)
from app.agents.planning import planning_metadata, select_planning_strategy
from app.agents.state import AgentState
from app.agents.workflow_execution import validate_workflow_plan, workflow_action_requested
from app.core.exceptions import (
    InvalidRequestError,
    LLMOutputError,
    LLMProviderError,
    LLMTruncationError,
)
from app.core.ids import new_id
from app.memory.context import node_context, node_query
from app.observability.tracing import span, traced
from app.prompts.planner import (
    PLANNER_FUNCTION_SYSTEM,
    PLANNER_FUNCTION_USER,
    PLANNER_SYSTEM,
    PLANNER_USER,
)
from app.providers.base import LLMProvider
from app.providers.fake import OfflineLLMProvider
from app.providers.json_parser import parse_model
from app.schemas.agent import AgentPlan, PlanStep, WorkflowAction
from app.schemas.chat import ActionProposal
from app.schemas.goals import GoalKind, TaskGoal
from app.skills.loader import match_skill
from app.skills.registry import SkillRegistry
from app.skills.schemas import SkillMetadata
from app.skills.selector import SkillSelection, affirmative_action, requests_item_return
from app.skills.workflow import WorkflowDefinition, compile_workflow
from app.tools.goal_contract import (
    ReadContract,
    enforce_read_calls,
    evaluate_read_contract,
    exclude_restricted_writes,
)
from app.tools.permissions import WRITE_RISKS
from app.tools.registry import ToolRegistry

_ORDER_RE = re.compile(r"ORD\d+", re.IGNORECASE)
_ALWAYS_AVAILABLE = ("search_knowledge", "escalate_to_human")


class Planner:
    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry,
        *,
        mode: DynamicPlanningMode = "json",
        original_tools: Mapping[str, dict[str, Any]] | None = None,
        strict: bool = False,
        skills: SkillRegistry | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._mode = mode
        self._original_tools = original_tools
        self._strict = strict
        self._skills = skills

    def _tool_catalog(self, allowed: set[str] | None = None) -> str:
        lines = []
        for tool in self._registry.all():
            if allowed is not None and tool.name not in allowed:
                continue
            description = (
                self._original_tools[tool.name]["function"]["description"]
                if self._original_tools is not None
                else tool.model_catalog_description()
            )
            lines.append(f"- {tool.name}: {description} [{tool.risk.value}]")
        return "\n".join(lines) or "- (no tools)"

    def _tool_definitions(self, allowed: set[str] | None) -> list[dict[str, Any]]:
        tools = [
            self._original_tools[tool.name]
            if self._original_tools is not None
            else tool.openai_schema()
            for tool in self._registry.all()
            if allowed is None or tool.name in allowed
        ]
        return strict_tool_definitions(tools) if self._strict else tools

    async def create_plan(
        self,
        query: str,
        intent_label: str,
        summary: str,
        *,
        task_goals: Sequence[TaskGoal] = (),
        skill_selection: SkillSelection | None = None,
    ) -> AgentPlan:
        contract = evaluate_read_contract(task_goals, self._registry)
        decision = select_planning_strategy(task_goals, contract)
        plan = AgentPlan(steps=[], rationale=decision.reason, read_contract_mode=contract.mode)
        instructions = None
        if skill_selection and skill_selection.name:
            if decision.strategy == "direct":
                self._skill_event("skill.fallback", skill_selection.name, "direct_precedence")
            elif decision.strategy != "clarify" or skill_selection.requires_agent:
                skill_plan, instructions = self._activate_skill(skill_selection, task_goals)
                if skill_plan is not None:
                    if skill_plan.planning_strategy == "clarify":
                        return skill_plan
                    decision = select_planning_strategy(
                        task_goals, contract, workflow_validated=True
                    )
                    return planning_metadata(
                        skill_plan, decision, task_goals, contract, llm_calls=0
                    )
        if (
            instructions
            and skill_selection
            and skill_selection.open_catalog
            and contract.mode == "clarify"
        ):
            # The selected, read-only catalog skill can discover the missing product first.
            contract = ReadContract()
            decision = select_planning_strategy(task_goals, contract)
        if decision.strategy == "clarify":
            return planning_metadata(plan, decision, task_goals, contract, llm_calls=0)
        llm_calls = 0
        contract_tools = (
            {call.name for call in contract.calls} if contract.calls is not None else None
        )
        if decision.strategy != "direct":
            if instructions:
                plan = await self._create_plan(
                    query,
                    intent_label,
                    summary,
                    contract_tools=contract_tools,
                    instructions=instructions,
                )
                plan.skill_name = instructions[0].name
                plan.skill_mode = "instructions"
            else:
                plan = await self._create_plan(
                    query, intent_label, summary, contract_tools=contract_tools
                )
            llm_calls = int(not isinstance(self._llm, OfflineLLMProvider))
            plan.planner_model_mode = self._mode if llm_calls else "none"
        plan = enforce_read_calls(plan, contract.calls, mode=contract.mode)
        return planning_metadata(plan, decision, task_goals, contract, llm_calls=llm_calls)

    @staticmethod
    def _skill_event(event: str, name: str, reason: str, *, kind: str = "none") -> None:
        with span(event, skill_name=name, skill_selection_reason=reason, skill_mode=kind):
            pass

    def _activate_skill(
        self, selected: SkillSelection, goals: Sequence[TaskGoal]
    ) -> tuple[AgentPlan | None, tuple[SkillMetadata, str] | None]:
        if self._skills is None or not selected.name:
            return None, None
        skill = self._skills.get(selected.name)
        if skill is None:
            return None, None
        if selected.clarification:
            return AgentPlan(
                steps=[],
                read_contract_mode="clarify",
                planning_strategy="clarify",
                planning_reason="skill_clarification",
                skill_name=skill.name,
                skill_clarification=selected.clarification,
            ), None
        try:
            body = self._skills.load_instructions(skill.name)
            if selected.use_workflow:
                definition = WorkflowDefinition.model_validate(
                    self._skills.load_workflow(skill.name)
                )
                plan = compile_workflow(definition, skill, selected, self._registry)
                validate_workflow_plan(plan, self._registry)
                if action := plan.workflow_action:
                    candidate = AgentPlan(
                        steps=[
                            PlanStep(
                                step_id=1,
                                goal="pending confirmation",
                                tool_name=action.tool_name,
                                arguments=action.arguments,
                            )
                        ]
                    )
                    if not exclude_restricted_writes(candidate, goals, self._registry).steps:
                        raise ValueError("Workflow approval violates the current task")
                self._skill_event(
                    "skill.activation", skill.name, selected.reason_code, kind="workflow"
                )
                return plan, None
            if selected.use_reference and skill.resources:
                body += "\n\n" + self._skills.load_resource(skill.name, skill.resources[0].path)
            self._skill_event(
                "skill.activation", skill.name, selected.reason_code, kind="instructions"
            )
            return None, (skill, body)
        except (ValueError, OSError, InvalidRequestError):
            reason = "invalid_workflow" if selected.use_workflow else "load_failed"
            self._skill_event("skill.fallback", skill.name, reason)
            if selected.use_workflow and skill.extensions.get("adaptive-activation") == "action":
                return AgentPlan(
                    steps=[],
                    read_contract_mode="clarify",
                    planning_strategy="clarify",
                    planning_reason="skill_clarification",
                    skill_name=skill.name,
                ), None
            return None, None

    async def _create_plan(
        self,
        query: str,
        intent_label: str,
        summary: str,
        *,
        contract_tools: set[str] | None,
        instructions: tuple[SkillMetadata, str] | None = None,
    ) -> AgentPlan:
        offline = isinstance(self._llm, OfflineLLMProvider)
        skill = match_skill(query, intent_label) if self._skills is None or offline else None
        allowed = (
            contract_tools
            if contract_tools is not None
            else _allowed_tools(skill, self._registry, query)
        )
        if instructions and contract_tools is None:
            allowed = (set(instructions[0].tools) | set(_ALWAYS_AVAILABLE)) & set(
                self._registry.names()
            )
        if offline:
            return (
                skill_to_plan(skill, query, self._registry)
                if skill
                else _knowledge_fallback(query, self._registry)
            )
        try:
            info = instructions[1] if instructions else _format_skill(skill, contract_tools)
            if self._mode == "function_calling":
                plan = await self._function_plan(query, intent_label, summary, info, allowed)
            else:
                plan = await self._json_plan(query, intent_label, summary, info, allowed)
            plan = _sanitize_plan(plan, self._registry, allowed)
            if plan.steps:
                if skill:
                    plan.rationale = f"skill:{skill['name']};{plan.rationale}"
                return plan
        except (LLMOutputError, LLMProviderError):
            pass
        if skill:
            return skill_to_plan(skill, query, self._registry)
        return _knowledge_fallback(query, self._registry)

    async def _json_plan(
        self, query: str, intent: str, summary: str, skill: str, allowed: set[str] | None
    ) -> AgentPlan:
        response = await self._llm.generate(
            [
                {
                    "role": "system",
                    "content": PLANNER_SYSTEM.format(
                        tools=self._tool_catalog(allowed),
                        skill_context=skill,
                    ),
                },
                {
                    "role": "user",
                    "content": PLANNER_USER.format(
                        query=query, intent=intent, summary=summary or "无"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        return parse_model(response.content, AgentPlan)

    async def _function_plan(
        self, query: str, intent: str, summary: str, skill: str, allowed: set[str] | None
    ) -> AgentPlan:
        tools = self._tool_definitions(allowed)
        if not tools:
            return AgentPlan(steps=[], rationale="no_registered_candidates")
        response = await cast(NativePlanningProvider, self._llm).generate(
            [
                {"role": "system", "content": PLANNER_FUNCTION_SYSTEM.format(skill_context=skill)},
                {
                    "role": "user",
                    "content": PLANNER_FUNCTION_USER.format(
                        query=query, intent=intent, summary=summary or "无"
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=512,
            tools=tools,
            tool_choice="auto",
        )
        if response.finish_reason == "length":
            raise LLMTruncationError()
        if response.finish_reason in {"content_filter", "insufficient_system_resource"}:
            raise LLMOutputError("DeepSeek native tool plan did not finish normally")
        return decode_native_plan(response.tool_calls).plan


def _skill_tools(skill: dict, query: str) -> list[str]:
    tools = list(skill.get("tools", []))
    # The appended entity hint requests a fresh observation; it is not a new
    # user request for status or shipment events.
    requested = query.partition("（会话指代：")[0]
    requested = re.sub(r"[\s?？!！。]+", "", requested)
    # Positive recognition of a complete, narrow order-header request. Unknown
    # wording or additional goals preserve shipment capability; a keyword such
    # as 状态 alone cannot prove that shipment evidence is unnecessary.
    status_only = re.fullmatch(
        r"(?:(?:请|帮我|麻烦)?(?:查询|查看|查|看下|看看))?"
        r"(?:我的)?(?:订单)?(?:ORD\d+|它|这单|那单|该订单|这个订单|那个订单)"
        r"(?:(?:现在|当前|最新|目前)?(?:的)?(?:是)?(?:什么)?(?:状态|支付状态|发货状态)"
        r"|(?:的)?金额(?:是多少|多少)?"
        r"|(?:现在|当前)?(?:是否|有没有)?已?(?:支付|发货)(?:成功|了)?吗?)",
        requested,
        re.I,
    )
    if skill.get("name") == "order_tracking" and status_only:
        tools = [name for name in tools if name != "track_shipment"]
    return tools


def _allowed_tools(skill: dict | None, registry: ToolRegistry, query: str = "") -> set[str] | None:
    if skill is None:
        return None
    names = set(registry.names())
    allowed = {name for name in _skill_tools(skill, query) if name in names}
    allowed.update(name for name in _ALWAYS_AVAILABLE if name in names)
    return allowed or None


def _format_skill(skill: dict | None, allowed: set[str] | None = None) -> str:
    if skill is None:
        return "无（通用工具集）"
    steps = "、".join(skill.get("steps") or [])
    tools = ", ".join(
        name for name in skill.get("tools") or [] if allowed is None or name in allowed
    )
    return f"{skill['name']}：{skill.get('description', '')}。步骤：{steps}。工具：{tools}"


def _sanitize_plan(
    plan: AgentPlan,
    registry: ToolRegistry,
    allowed: set[str] | None,
) -> AgentPlan:
    names = set(registry.names())
    if allowed is not None:
        names = names & allowed
    steps = [
        step
        for step in plan.steps
        if not (step.depends_on or step.condition)
        and (not step.tool_name or step.tool_name in names)
    ]
    return AgentPlan(steps=steps[:6], rationale=plan.rationale)


def _validated_skill_steps(
    plan: AgentPlan, goals: Sequence[TaskGoal], registry: ToolRegistry, query: str
) -> list[PlanStep]:
    kinds = {"cancel_order": GoalKind.CANCEL, "create_return_request": GoalKind.RETURN_REQUEST}
    steps = []
    for step in plan.steps:
        if not step.tool_name or registry.get(step.tool_name).risk not in WRITE_RISKS:
            steps.append(step)
        elif step.tool_name in kinds and step.arguments.get("order_id"):
            action = WorkflowAction(
                tool_name=step.tool_name, arguments=step.arguments, source_step_id=1
            )
            return_reason = action.arguments.get("reason")
            valid_scope = step.tool_name != "create_return_request" or (
                not requests_item_return(query)
                and isinstance(return_reason, str)
                and return_reason.strip()
                and return_reason in query
            )
            if (
                valid_scope
                and workflow_action_requested(action, goals)
                and any(
                    goal.kind == kinds[step.tool_name]
                    and goal.entity_id == step.arguments["order_id"]
                    and affirmative_action(query, goal)
                    for goal in goals
                )
            ):
                steps.append(step)
        elif step.tool_name not in kinds and plan.skill_mode != "instructions":
            steps.append(step)
    return steps


def skill_to_plan(skill: dict, query: str, registry: ToolRegistry) -> AgentPlan:
    steps: list[PlanStep] = []
    for index, tool_name in enumerate(_skill_tools(skill, query), start=1):
        if tool_name not in registry.names():
            continue
        steps.append(
            PlanStep(
                step_id=index,
                goal=skill["name"],
                tool_name=tool_name,
                arguments=_tool_arguments(tool_name, query),
                needs_retrieval=tool_name == "search_knowledge",
            )
        )
    if steps:
        return AgentPlan(steps=steps, rationale=f"skill:{skill['name']}")
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
        plan = AgentPlan(
            steps=[
                PlanStep(
                    step_id=1,
                    goal="confirmed action",
                    tool_name=confirmed.tool_name,
                    arguments=confirmed.arguments,
                )
            ],
            rationale="confirmed_action",
            planning_strategy="confirmed",
            planning_reason="confirmed_action",
        )
        _trace_planning(plan, ())
        return {"plan": plan, "pending_action": None}
    intent = state.get("intent")
    goals = state.get("task_goals", ())
    context = state.get("selected_context")
    if context and context.needs_clarification:
        plan = AgentPlan(
            steps=[],
            read_contract_mode="clarify",
            planning_strategy="clarify",
            planning_reason="entity_ambiguity",
        )
        _trace_planning(plan, goals)
        return {"plan": plan, "pending_action": None}
    plan = await planner.create_plan(
        node_query(state),
        intent.label.value if intent else "faq_policy",
        node_context(state, "planner")
        if state.get("memory_managed")
        else state.get("summary") or "",
        task_goals=goals,
        skill_selection=state.get("skill_selection"),
    )
    plan = exclude_restricted_writes(plan, goals, planner._registry)
    if planner._skills is not None:
        plan = plan.model_copy(
            update={
                "steps": _validated_skill_steps(plan, goals, planner._registry, state["user_query"])
            }
        )
    write_steps = [
        step
        for step in plan.steps
        if step.tool_name and planner._registry.get(step.tool_name).risk in WRITE_RISKS
    ]
    if any(
        _explicit_write_request(state["user_query"], step.tool_name or "") for step in write_steps
    ):
        if any(not step.arguments.get("order_id") for step in write_steps):
            plan = plan.model_copy(
                update={
                    "steps": [],
                    "planning_strategy": "clarify",
                    "planning_reason": "entity_ambiguity",
                }
            )
            _trace_planning(plan, goals)
            return {
                "plan": plan,
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
                summary=action_summary(tool.name, step.arguments),
            )
            break
    _trace_planning(plan, goals)
    return {"plan": plan, "pending_action": pending}


def _trace_planning(plan: AgentPlan, goals: Sequence[TaskGoal]) -> None:
    tools = [step.tool_name for step in plan.steps if step.tool_name]
    with span(
        "planner.strategy",
        planning_strategy=plan.planning_strategy,
        planning_reason=plan.planning_reason,
        goal_kinds=[goal.kind.value for goal in goals if not goal.negated],
        planned_tools=tools,
        planned_tool_count=len(tools),
        planner_llm_calls=plan.planner_llm_calls,
        planner_model_mode=plan.planner_model_mode,
        skill_name=plan.skill_name,
        skill_mode=plan.skill_mode,
        planning_required_goals=plan.planning_required_goals,
        planning_covered_goals=plan.planning_covered_goals,
        planning_deduplicated_calls=plan.planning_deduplicated_calls,
    ):
        pass


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
