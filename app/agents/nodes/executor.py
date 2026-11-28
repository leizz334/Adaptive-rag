"""Tool execution node with argument fallback and retries."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass

from app.agents.goal_answers import find_goal_observation
from app.agents.state import AgentState
from app.agents.workflow_execution import (
    Decision,
    is_workflow_plan,
    prepare_workflow_proposal,
    validate_workflow_plan,
    workflow_action_requested,
    workflow_gate,
)
from app.config.settings import Settings
from app.core.enums import ToolRisk
from app.core.exceptions import (
    AppError,
    InvalidRequestError,
    ToolExecutionError,
    ToolPermissionError,
)
from app.core.request_scope import get_db_session
from app.memory.context import trace_context
from app.observability.execution import record_tool
from app.observability.metrics import TOOL_CALLS
from app.observability.tracing import safe_metadata, span, traced
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.agent import AgentPlan, PlanStep, ToolResult, WorkflowStepStatus
from app.schemas.common import LatencyBreakdown
from app.schemas.goals import TaskGoal
from app.tools.base import Tool, ToolContext
from app.tools.permissions import WRITE_RISKS, assert_permitted
from app.tools.registry import ToolRegistry

READ_FALLBACKS: dict[str, list[str]] = {
    "get_order": ["search_knowledge"],
    "get_order_items": ["get_order", "search_knowledge"],
    "track_shipment": ["get_order", "search_knowledge"],
    "get_product_detail": ["search_products", "search_knowledge"],
    "search_products": ["search_knowledge"],
    "recommend_products": ["search_products", "search_knowledge"],
    "get_coupon": ["search_knowledge"],
    "get_warranty": ["search_knowledge"],
    "get_refund_status": ["search_knowledge"],
    "check_inventory": ["search_products", "search_knowledge"],
    "mcp_store_hours": ["search_knowledge"],
    "mcp_warehouse_cutoff": ["search_knowledge"],
}


@dataclass
class _ToolCallBudget:
    limit: int
    used: int = 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def _fingerprint(tool_name: str, arguments: dict) -> str:
    payload = json.dumps(
        {"tool": tool_name, "arguments": arguments}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def fallback_arguments(tool_name: str, step: PlanStep, query: str) -> dict:
    if tool_name == "search_knowledge":
        return {"query": query[:200]}
    if tool_name in {"search_products", "recommend_products"}:
        return {"query": (step.arguments.get("query") or query)[:80]}
    return dict(step.arguments)


async def execute_with_fallback(
    tool: Tool,
    step: PlanStep,
    context: ToolContext,
    registry: ToolRegistry,
    query: str,
    *,
    allow_fallback: bool = True,
    budget: _ToolCallBudget | None = None,
) -> ToolResult:
    """Execution-layer fallback: a failed read tool tries the next mapped tool."""
    try:
        result = await tool.run(step.arguments, context)
        if result.success:
            return result
        raise ToolExecutionError(result.error or f"{tool.name} returned success=false")
    except (ToolPermissionError, InvalidRequestError):
        # A deterministic business/argument rejection cannot be repaired by
        # asking another tool for the same protected entity.
        raise
    except AppError as exc:
        if not allow_fallback:
            raise
        last_error = str(exc)
        for fallback_name in READ_FALLBACKS.get(tool.name, []):
            if fallback_name not in registry.names():
                continue
            if budget is not None and not budget.take():
                break
            fallback = registry.get(fallback_name)
            try:
                fb_result = await fallback.run(
                    fallback_arguments(fallback_name, step, query), context
                )
                if fb_result.success:
                    merged = {
                        **fb_result.output,
                        "fallback_from": tool.name,
                        "fallback_error": last_error,
                    }
                    TOOL_CALLS.labels(tool=fallback_name, status="fallback").inc()
                    return fb_result.model_copy(update={"output": merged})
            except (ToolPermissionError, InvalidRequestError):
                raise
            except AppError:
                continue
        raise


@traced("node.executor", "chain")
async def executor_node(
    state: AgentState,
    *,
    registry: ToolRegistry,
    settings: Settings,
) -> dict:
    plan = state.get("plan")
    if plan is None:
        return {"tool_results": []}
    if (memory := state.get("selected_context")) and memory.structured:
        trace_context(
            "executor", plan.model_dump_json(exclude={"rationale"}), ("plan", "permissions")
        )
    if state.get("pending_action") and not state.get("confirm_action_id"):
        _trace_execution(plan, state.get("task_goals", ()), (), ())
        return {"tool_results": []}
    workflow = is_workflow_plan(plan)
    if workflow:
        try:
            validate_workflow_plan(plan, registry)
            if plan.workflow_action and not workflow_action_requested(
                plan.workflow_action, state.get("task_goals", ())
            ):
                raise InvalidRequestError("workflow confirmation does not match the task")
        except InvalidRequestError:
            with span("skill.workflow.rejected", workflow_error="invalid_plan"):
                pass
            return {"tool_results": [], "workflow_error": "invalid_plan"}

    started = time.perf_counter()
    results: list[ToolResult] = []
    result_steps: list[int] = []
    workflow_results: dict[int, ToolResult] = {}
    workflow_statuses: dict[int, WorkflowStepStatus] = {}
    bounded = plan.read_contract_mode in {"full", "partial"}
    context = ToolContext(
        user_id=state["user_id"],
        session_id=state["session_id"],
        trace_id=state["trace_id"],
        confirmed_action_id=state.get("confirm_action_id"),
        idempotency_key=state.get("idempotency_key"),
    )
    idempotency = IdempotencyRepository(get_db_session())
    initial_step_count = state.get("step_count") or 0
    budget = _ToolCallBudget(
        min(settings.max_tool_calls, settings.max_agent_steps) - initial_step_count
    )
    query = state["user_query"]
    for step in plan.steps:
        if budget.used >= budget.limit:
            if workflow:
                workflow_statuses[step.step_id] = "limit_reached"
                _trace_workflow_step(step, "limit_reached")
                continue
            break
        if not step.tool_name:
            continue
        decision = None
        if workflow:
            skipped, decision = workflow_gate(
                step, workflow_statuses, workflow_results, context.user_id
            )
            if skipped is not None:
                workflow_statuses[step.step_id] = skipped
                _trace_workflow_step(step, skipped, decision)
                continue
        tool = registry.get(step.tool_name)
        if state.get("react_read_only") and tool.risk != ToolRisk.READ:
            continue
        budget.take()
        confirmed = bool(state.get("confirm_action_id"))
        try:
            if tool.risk in WRITE_RISKS:
                assert_permitted(tool, confirmed=confirmed)
                idem_key = context.confirmed_action_id or context.idempotency_key
                if idem_key:
                    fp = _fingerprint(tool.name, step.arguments)
                    existing = await idempotency.get_if_matches(idem_key, fp)
                    if existing is not None:
                        record_tool(tool.name, step.arguments, status="replayed", output=existing)
                        results.append(
                            ToolResult(
                                name=tool.name, success=True, output=existing, risk=tool.risk
                            )
                        )
                        TOOL_CALLS.labels(tool=tool.name, status="idempotent").inc()
                        continue
                    result = await tool.run(step.arguments, context)
                    if result.success:
                        await idempotency.put(idem_key, fp, result.output)
                    TOOL_CALLS.labels(
                        tool=tool.name, status="ok" if result.success else "error"
                    ).inc()
                    results.append(result)
                    continue
            result = await execute_with_fallback(
                tool,
                step,
                context,
                registry,
                query,
                allow_fallback=not (bounded or workflow or state.get("react_read_only")),
                budget=budget,
            )
            TOOL_CALLS.labels(tool=tool.name, status="ok").inc()
            results.append(result)
        except ToolPermissionError as exc:
            record_tool(
                tool.name,
                step.arguments,
                success=False,
                status="denied",
                failure_kind="permission_denied",
            )
            TOOL_CALLS.labels(tool=tool.name, status="denied").inc()
            results.append(
                ToolResult(name=tool.name, success=False, error=str(exc), risk=tool.risk)
            )
        except AppError as exc:
            if exc.error_code.value == "IDEMPOTENCY_CONFLICT":
                TOOL_CALLS.labels(tool=tool.name, status="conflict").inc()
            else:
                TOOL_CALLS.labels(tool=tool.name, status="error").inc()
            results.append(
                ToolResult(name=tool.name, success=False, error=str(exc), risk=tool.risk)
            )
        result_steps.append(step.step_id)
        if workflow:
            tool_result = results[-1]
            outcome: WorkflowStepStatus = "executed" if tool_result.success else "failed"
            workflow_statuses[step.step_id] = outcome
            workflow_results[step.step_id] = tool_result
            _trace_workflow_step(step, outcome, decision)
    latency = state.get("latency") or LatencyBreakdown()
    latency.tool_ms = (time.perf_counter() - started) * 1000
    _trace_execution(plan, state.get("task_goals", ()), results, result_steps, attempts=budget.used)
    updates = {
        "tool_results": results,
        "tool_result_steps": result_steps,
        "step_count": initial_step_count + budget.used,
        "latency": latency,
    }
    if workflow:
        updates["workflow_step_statuses"] = workflow_statuses
    if action := plan.workflow_action:
        status, pending = prepare_workflow_proposal(
            action, workflow_results.get(action.source_step_id), registry, context.user_id
        )
        with span("skill.workflow.proposal", workflow_action_status=status):
            pass
        updates.update(workflow_action_status=status, pending_action=pending)
    return updates


def _trace_workflow_step(
    step: PlanStep, status: WorkflowStepStatus, decision: Decision | None = None
) -> None:
    with span(
        "skill.workflow.step",
        workflow_step_id=step.step_id,
        workflow_source_step_id=step.condition.source_step_id if step.condition else None,
        workflow_step_status=status,
        workflow_condition_outcome=decision,
        planned_tools=[step.tool_name],
    ):
        pass


def _trace_execution(
    plan: AgentPlan,
    goals: Sequence[TaskGoal],
    results: Sequence[ToolResult],
    step_ids: Sequence[int],
    *,
    attempts: int = 0,
) -> None:
    with span(
        "planner.execution",
        planning_strategy=plan.planning_strategy,
        skill_name=plan.skill_name,
        skill_mode=plan.skill_mode,
    ) as event:
        if event is None:
            return
        reads = [goal for goal in goals if not goal.negated and goal.operation != "write"]
        observed = [
            find_goal_observation(goal, plan, results, step_ids) is not None for goal in reads
        ]
        missing = [
            goal.kind.value
            for goal, present in zip(reads, observed, strict=True)
            if not present or goal.unavailable_fields
        ]
        event.metadata.update(
            safe_metadata(
                {
                    "tool_attempt_count": attempts,
                    "successful_tool_count": sum(result.success for result in results),
                    "executed_tools": [result.name for result in results],
                    "observed_goal_count": sum(observed),
                    "missing_goal_count": len(missing),
                    "missing_evidence_kinds": missing,
                    "unavailable_field_count": sum(len(goal.unavailable_fields) for goal in reads),
                }
            )
        )
