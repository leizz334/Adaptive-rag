"""Bounded, evidence-driven continuation for read-only Dynamic catalog plans."""

from __future__ import annotations

import re
from typing import Any

from app.agents.nodes.executor import executor_node
from app.agents.state import AgentState
from app.agents.workflow_execution import is_workflow_plan, validate_tool_arguments
from app.config.settings import Settings
from app.core.enums import ToolRisk
from app.core.exceptions import InvalidRequestError
from app.memory.task_memory import SKU_PATTERN
from app.observability.tracing import span, traced
from app.schemas.agent import AgentPlan, PlanStep, ToolResult
from app.schemas.goals import GoalKind
from app.tools.registry import ToolRegistry

MAX_REPLANS = 2
_CATALOG_FIELDS = {"name": str, "description": str, "price_cents": int, "inventory": int}
_PRODUCT_CONSUMERS = {"get_product_detail", "check_inventory", "get_warranty"}
_WARRANTY = re.compile(r"通用(?:的)?保修|保修(?:摘要|期)")
_UNVERIFIED_SCOPE = re.compile(r"如果|除非|只有|仅在|不要|别查|不查|无需|不需要|没必要")


def _remaining_fields(state: AgentState) -> tuple[set[str], bool]:
    fields = {
        field
        for goal in state.get("task_goals", ())
        if not goal.negated
        and goal.kind
        in {
            GoalKind.PRODUCT_DETAIL,
            GoalKind.PRODUCT_PRICE,
            GoalKind.INVENTORY,
        }
        for field in goal.fields
        if field in _CATALOG_FIELDS
    }
    warranty = bool(_WARRANTY.search(state["user_query"]))
    return fields, warranty


def _admitted(plan: AgentPlan, state: AgentState, registry: ToolRegistry) -> bool:
    query = state["user_query"]
    known = set(registry.names())
    return (
        plan.planning_strategy == "dynamic"
        and plan.read_contract_mode == "legacy"
        and not is_workflow_plan(plan)
        and not (
            state.get("confirmed_action") or state.get("pending_action") or state.get("refused")
        )
        and not SKU_PATTERN.search(query)
        and not _UNVERIFIED_SCOPE.search(query)
        and not any(
            goal.operation == "write" or goal.conditions or goal.entity_type == "order"
            for goal in state.get("task_goals", ())
        )
        and any(step.tool_name == "search_products" for step in plan.steps)
        and all(
            step.tool_name in known and registry.get(step.tool_name).risk == ToolRisk.READ
            for step in plan.steps
            if step.tool_name
        )
    )


def _catalog_item(
    query: str, steps: list[PlanStep], results: dict[int, ToolResult]
) -> dict[str, Any] | None:
    sources = [
        (step, result)
        for step in steps
        if step.tool_name == "search_products" and (result := results.get(step.step_id))
    ]
    if len(sources) != 1:
        return None
    step, result = sources[0]
    if not (
        result.name == step.tool_name
        and result.success
        and not result.truncated
        and "fallback_from" not in result.output
    ):
        return None
    keyword = step.arguments.get("query")
    products = result.output.get("products")
    if (
        not isinstance(keyword, str)
        or not keyword.strip()
        or keyword.casefold() not in query.casefold()
        or not isinstance(products, list)
        or len(products) != 1
        or not isinstance(products[0], dict)
    ):
        return None
    item = products[0]
    if (
        not isinstance(sku := item.get("sku"), str)
        or not SKU_PATTERN.fullmatch(sku)
        or not isinstance(name := item.get("name"), str)
        or keyword.casefold() not in name.casefold()
    ):
        return None
    return item


def _available_fields(value: dict) -> set[str]:
    available = set()
    for field, kind in _CATALOG_FIELDS.items():
        item = value.get(field)
        if kind is int and type(item) is int and item >= 0:
            available.add(field)
        elif kind is str and isinstance(item, str) and item.strip():
            available.add(field)
    return available


def _stop(reason: str) -> None:
    with span("react.stop", react_stop_reason=reason):
        pass


@traced("node.dynamic_execution", "chain")
async def execute_with_replanning(
    state: AgentState, *, registry: ToolRegistry, settings: Settings
) -> dict:
    plan = state.get("plan")
    if not settings.react_enabled or plan is None or not _admitted(plan, state, registry):
        return await executor_node(state, registry=registry, settings=settings)
    fields, warranty = _remaining_fields(state)
    if not fields and not warranty:
        return await executor_node(state, registry=registry, settings=settings)

    # A Dynamic placeholder cannot authorize a consumer before directory resolution.
    steps = [
        step.model_copy(update={"step_id": index})
        for index, step in enumerate(
            (step for step in plan.steps if step.tool_name not in _PRODUCT_CONSUMERS), start=1
        )
    ]
    current = plan.model_copy(update={"steps": steps})
    updates = await executor_node(
        {**state, "plan": current, "react_read_only": True}, registry=registry, settings=settings
    )
    results = list(updates["tool_results"])
    observed_steps = list(updates["tool_result_steps"])
    item = _catalog_item(
        state["user_query"], steps, dict(zip(observed_steps, results, strict=True))
    )
    if item is None or any(not result.success for result in results):
        _stop("unverified_catalog")
        return {**updates, "plan": current}

    sku = item["sku"]
    missing = fields - _available_fields(item)
    tried: set[tuple[str, str]] = set()
    reason = "round_limit"
    for round_number in range(1, MAX_REPLANS + 1):
        if not missing and not warranty:
            reason = "evidence_complete"
            break
        if updates["step_count"] >= min(settings.max_tool_calls, settings.max_agent_steps):
            reason = "tool_budget"
            break
        name = "get_product_detail" if missing else "get_warranty"
        if (name, sku) in tried:
            reason = "repeated_call"
            break
        if name not in registry.names() or registry.get(name).risk != ToolRisk.READ:
            reason = "invalid_next_step"
            break
        tool = registry.get(name)
        step = PlanStep(
            step_id=len(steps) + 1,
            goal="verify remaining catalogue evidence",
            tool_name=name,
            arguments={"sku": sku},
        )
        try:
            validate_tool_arguments(tool, step.arguments)
        except InvalidRequestError:
            reason = "invalid_next_step"
            break
        tried.add((name, sku))
        elapsed = updates["latency"].tool_ms
        with span("react.round", react_round=round_number, planned_tools=(name,)):
            following = await executor_node(
                {
                    **state,
                    **updates,
                    "plan": current.model_copy(update={"steps": [step]}),
                    "react_read_only": True,
                },
                registry=registry,
                settings=settings,
            )
        steps.append(step)
        results.extend(following["tool_results"])
        observed_steps.extend(following["tool_result_steps"])
        updates = following
        updates["latency"].tool_ms += elapsed
        outcome = following["tool_results"]
        if len(outcome) != 1 or not outcome[0].success or outcome[0].truncated:
            reason = "tool_failed"
            break
        fresh = outcome[0]
        if fresh.name != name or fresh.output.get("sku") != sku:
            reason = "no_progress"
            break
        before = (frozenset(missing), warranty)
        if name == "get_product_detail":
            missing -= _available_fields(fresh.output)
        elif type(months := fresh.output.get("warranty_months")) is int and months >= 0:
            warranty = False
        if (frozenset(missing), warranty) == before:
            reason = "no_progress"
            break
    else:
        if not missing and not warranty:
            reason = "evidence_complete"
    _stop(reason)
    return {
        **updates,
        "plan": current.model_copy(update={"steps": steps}),
        "tool_results": results,
        "tool_result_steps": observed_steps,
    }
