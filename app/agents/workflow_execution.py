"""Validation and typed evidence checks for bounded skill plans."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal

from app.agents.action_proposals import action_summary
from app.core.enums import OrderStatus, ToolRisk
from app.core.exceptions import InvalidRequestError
from app.core.ids import new_id
from app.schemas.agent import (
    AgentPlan,
    PlanStep,
    ToolResult,
    WorkflowAction,
    WorkflowActionStatus,
    WorkflowStepStatus,
)
from app.schemas.chat import ActionProposal
from app.schemas.goals import GoalKind, TaskGoal
from app.tools.base import Tool
from app.tools.permissions import WRITE_RISKS
from app.tools.registry import ToolRegistry

MAX_WORKFLOW_STEPS = 6
Decision = Literal["true", "false", "unknown", "unavailable"]
_ORDER_STATUSES = frozenset(status.value for status in OrderStatus)
_PROPOSABLE_WRITES = {
    "cancel_order": GoalKind.CANCEL,
    "create_return_request": GoalKind.RETURN_REQUEST,
}


def is_workflow_plan(plan: AgentPlan) -> bool:
    return (
        plan.skill_mode == "workflow"
        or plan.workflow_action is not None
        or any(step.depends_on or step.condition is not None for step in plan.steps)
    )


def validate_tool_arguments(tool: Tool, arguments: dict) -> None:
    if not arguments.keys() <= tool.input_model.model_fields.keys():
        raise InvalidRequestError("unexpected tool arguments")
    tool.parse(arguments)


def validate_workflow_plan(plan: AgentPlan, registry: ToolRegistry) -> None:
    """Reject the entire workflow before executing any malformed or unsafe binding."""
    if (
        plan.skill_mode != "workflow"
        or not plan.skill_name
        or not 0 < len(plan.steps) <= MAX_WORKFLOW_STEPS
    ):
        raise InvalidRequestError("invalid workflow metadata or size")

    visited: dict[int, PlanStep] = {}
    for step in plan.steps:
        if (
            step.step_id < 1
            or step.step_id in visited
            or not set(step.depends_on) <= visited.keys()
            or len(step.depends_on) != len(set(step.depends_on))
            or not step.tool_name
        ):
            raise InvalidRequestError("invalid workflow step or dependency")
        tool = registry.get(step.tool_name)
        if tool.risk != ToolRisk.READ:
            raise InvalidRequestError("workflow steps must be read-only")
        validate_tool_arguments(tool, step.arguments)
        if condition := step.condition:
            if (
                condition.source_step_id not in step.depends_on
                or condition.field != "paid_at"
                or condition.op != "is_paid"
                or not _same_order_source(
                    visited[condition.source_step_id], step.arguments.get("order_id")
                )
            ):
                raise InvalidRequestError("invalid workflow condition source")
        visited[step.step_id] = step

    if action := plan.workflow_action:
        order_id = action.arguments.get("order_id")
        source = visited.get(action.source_step_id)
        if (
            action.tool_name not in _PROPOSABLE_WRITES
            or source is None
            or source.depends_on
            or not _same_order_source(source, order_id)
        ):
            raise InvalidRequestError("invalid workflow confirmation source")
        tool = registry.get(action.tool_name)
        if tool.risk not in WRITE_RISKS:
            raise InvalidRequestError("invalid workflow confirmation risk")
        validate_tool_arguments(tool, action.arguments)


def _same_order_source(step: PlanStep, order_id: object) -> bool:
    return (
        isinstance(order_id, str)
        and step.tool_name == "get_order"
        and step.arguments.get("order_id") == order_id
    )


def workflow_action_requested(action: WorkflowAction, goals: Sequence[TaskGoal]) -> bool:
    """A proposal requires the same safe scope as the resolved user action."""
    kind = _PROPOSABLE_WRITES[action.tool_name]
    if any(
        (goal.kind == kind and goal.negated) or (goal.operation != "read" and goal.conditions)
        for goal in goals
    ):
        return False
    return any(
        goal.kind == kind
        and goal.operation == "write"
        and goal.entity_id == action.arguments["order_id"]
        and goal.entity_source != "none"
        and not goal.clarification
        for goal in goals
    )


def _visible_order(result: ToolResult, order_id: str, user_id: str) -> bool:
    return (
        result.name == "get_order"
        and result.risk == ToolRisk.READ
        and result.success
        and not result.truncated
        and "fallback_from" not in result.output
        and result.output.get("order_id") == order_id
        and result.output.get("user_id") == user_id
    )


def _payment_evidence(result: ToolResult | None, order_id: str, user_id: str) -> Decision:
    if result is None or not _visible_order(result, order_id, user_id):
        return "unknown"
    status = result.output.get("status")
    if (
        not isinstance(status, str)
        or status not in _ORDER_STATUSES
        or "paid_at" not in result.output
    ):
        return "unknown"
    paid_at = result.output["paid_at"]
    if status == OrderStatus.CREATED:
        return "false" if paid_at is None else "unknown"
    if not isinstance(paid_at, str) or "T" not in paid_at:
        return "unknown"
    try:
        datetime.fromisoformat(paid_at)
    except ValueError:
        return "unknown"
    return "true"


def workflow_gate(
    step: PlanStep,
    statuses: Mapping[int, WorkflowStepStatus],
    results: Mapping[int, ToolResult],
    user_id: str,
) -> tuple[WorkflowStepStatus | None, Decision | None]:
    condition = step.condition
    dependencies = [statuses.get(step_id) for step_id in step.depends_on]
    if any(status in {"failed", "prerequisite_failed"} for status in dependencies):
        return "prerequisite_failed", "unavailable" if condition else None
    if any(status != "executed" for status in dependencies):
        return "prerequisite_skipped", "unavailable" if condition else None
    if condition is None:
        return None, None
    decision = _payment_evidence(
        results.get(condition.source_step_id), step.arguments["order_id"], user_id
    )
    if decision == "false":
        return "condition_false", decision
    if decision != "true":
        return "condition_unknown", decision
    return None, decision


def prepare_workflow_proposal(
    action: WorkflowAction, result: ToolResult | None, registry: ToolRegistry, user_id: str
) -> tuple[WorkflowActionStatus, ActionProposal | None]:
    if result is None:
        return "unverified", None
    if not result.success:
        return "failed", None
    if not _visible_order(result, action.arguments["order_id"], user_id):
        return "unverified", None
    if action.tool_name == "cancel_order":
        status = result.output.get("status")
        if not isinstance(status, str) or status not in _ORDER_STATUSES:
            return "unverified", None
        if status not in {OrderStatus.CREATED, OrderStatus.PAID}:
            return "ineligible", None
    tool = registry.get(action.tool_name)
    arguments = tool.parse(action.arguments).model_dump()
    return "ready", ActionProposal(
        action_id=new_id("act_"),
        tool_name=tool.name,
        arguments=arguments,
        risk=tool.risk,
        summary=action_summary(tool.name, arguments),
    )
