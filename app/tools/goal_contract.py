"""Goal-to-tool capabilities and checks for actual observations.

The mapping is independent of skills, planner wording and evaluation cases.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.core.enums import OrderStatus, ToolRisk
from app.core.exceptions import InvalidRequestError
from app.schemas.agent import AgentPlan, PlanStep, ReadContractMode, ToolResult
from app.schemas.goals import GoalKind, TaskGoal, goal_read_fields
from app.tools.permissions import WRITE_RISKS
from app.tools.registry import ToolRegistry

G = GoalKind


@dataclass(frozen=True)
class ToolCapability:
    argument: str
    goals: frozenset[GoalKind]
    returned_entity: str | None = None
    risk: ToolRisk = ToolRisk.READ


CAPABILITIES = {
    "get_order": ToolCapability(
        "order_id", frozenset({G.ORDER_STATUS, G.ORDER_AMOUNT, G.ORDER_PAYMENT}), "order_id"
    ),
    "get_order_items": ToolCapability("order_id", frozenset({G.ORDER_ITEMS})),
    "track_shipment": ToolCapability(
        "order_id", frozenset({G.SHIPMENT, G.TRACKING_NUMBER}), "order_id"
    ),
    "get_refund_status": ToolCapability("order_id", frozenset({G.REFUND_STATUS})),
    "check_inventory": ToolCapability("sku", frozenset({G.INVENTORY}), "sku"),
    "get_product_detail": ToolCapability(
        "sku", frozenset({G.PRODUCT_DETAIL, G.PRODUCT_PRICE, G.INVENTORY}), "sku"
    ),
    "search_knowledge": ToolCapability("query", frozenset({G.POLICY})),
}
_PREFERRED = {goal: name for name, cap in CAPABILITIES.items() for goal in cap.goals}
_PREFERRED[G.INVENTORY] = "check_inventory"


@dataclass(frozen=True)
class BoundRead:
    name: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class ReadContract:
    mode: ReadContractMode = "legacy"
    calls: list[BoundRead] | None = None


def call_covers_goal(call: BoundRead, goal: TaskGoal) -> bool:
    """Check that a call is bound to this goal and can return all requested facts."""
    capability = CAPABILITIES.get(call.name)
    expected = goal.request_text if goal.kind == G.POLICY else goal.entity_id
    return (
        capability is not None
        and goal.kind in capability.goals
        and goal.operation == "read"
        and not (goal.negated or goal.conditions or goal.clarification)
        and bool(goal.fields)
        and set(goal.fields).issubset(goal_read_fields(goal.kind))
        and bool(expected)
        and call.arguments.get(capability.argument) == expected
    )


def required_read_calls(
    goals: Sequence[TaskGoal], registry: ToolRegistry
) -> list[BoundRead] | None:
    """Constrain only fully grounded read requests supported by the active registry."""
    active = [goal for goal in goals if not goal.negated]
    if not any(goal.entity_id for goal in active):
        return None
    return _bind_read_calls(active, registry)


def _bind_read_calls(active: Sequence[TaskGoal], registry: ToolRegistry) -> list[BoundRead] | None:
    detail_skus = {
        goal.entity_id for goal in active if goal.kind in {G.PRODUCT_DETAIL, G.PRODUCT_PRICE}
    }
    bindings: dict[tuple[str, str], BoundRead] = {}
    for goal in active:
        if goal.operation != "read" or goal.conditions or goal.clarification:
            return None
        name = _PREFERRED.get(goal.kind)
        if goal.kind == G.INVENTORY and goal.entity_id in detail_skus:
            name = "get_product_detail"
        if not name or name not in registry.names():
            return None
        capability = CAPABILITIES[name]
        tool = registry.get(name)
        key = goal.request_text if goal.kind == G.POLICY else goal.entity_id
        if not key or tool.risk != capability.risk:
            return None
        arguments = {capability.argument: key}
        try:
            parsed = tool.parse(arguments).model_dump()
        except InvalidRequestError:
            return None
        if parsed.keys() != arguments.keys() or not isinstance(parsed[capability.argument], str):
            return None
        call = BoundRead(name, parsed)
        if not call_covers_goal(call, goal):
            return None
        bindings.setdefault((name, parsed[capability.argument]), call)
    return list(bindings.values()) if len(bindings) <= 6 else None


def evaluate_read_contract(goals: Sequence[TaskGoal], registry: ToolRegistry) -> ReadContract:
    active = [goal for goal in goals if not goal.negated]
    facts = [goal for goal in active if goal.kind in _PREFERRED and goal.kind != G.POLICY]
    if not facts or any(goal.operation == "write" for goal in active):
        return ReadContract()
    if any(goal.conditions for goal in active):
        independent = [goal for goal in facts if goal.independent and not goal.conditions]
        if independent and (calls := _bind_read_calls(independent, registry)):
            return ReadContract("partial", calls)
        return ReadContract("clarify")
    missing = [goal for goal in facts if not goal.entity_id]
    if any(not goal.independent for goal in missing):
        # Product discovery by name has a dynamic path even without a catalog identifier.
        requires_identifier = any(goal.entity_type == "order" for goal in missing) or any(
            goal.entity_id or goal.unavailable_fields for goal in facts
        )
        return ReadContract("clarify" if requires_identifier else "legacy")
    unknown = [goal for goal in active if goal.kind not in _PREFERRED]
    unavailable = any(goal.unavailable_fields for goal in facts)
    if any(
        goal.kind != G.UNKNOWN or goal.operation == "write" or not goal.independent
        for goal in unknown
    ):
        return ReadContract("clarify")
    partial = bool(unknown or unavailable or missing)
    if partial and any(goal.kind == G.POLICY for goal in active):
        # Partial policy claims need the existing citation and relevance checks.
        return ReadContract("clarify")
    supported = [
        goal for goal in active if goal.kind in _PREFERRED and goal.fields and goal not in missing
    ]
    if any(not set(goal.fields).issubset(goal_read_fields(goal.kind)) for goal in supported):
        return ReadContract("clarify")
    calls = _bind_read_calls(supported, registry)
    if calls is None:
        return ReadContract("clarify" if partial else "legacy")
    if missing and not calls:
        return ReadContract("clarify")
    return ReadContract("partial" if partial else "full", calls)


def enforce_read_calls(
    plan: AgentPlan, required: list[BoundRead] | None, *, mode: ReadContractMode = "full"
) -> AgentPlan:
    """Keep matching model steps, remove excess calls and repair missing reads once."""
    if required is None:
        return plan
    steps = []
    for index, call in enumerate(required, start=1):
        step = next(
            (
                step
                for step in plan.steps
                if step.tool_name == call.name and step.arguments == call.arguments
            ),
            None,
        )
        if step is None:
            step = PlanStep(
                step_id=index,
                goal="required evidence",
                tool_name=call.name,
                arguments=call.arguments,
                needs_retrieval=call.name == "search_knowledge",
            )
        steps.append(step.model_copy(update={"step_id": index}))
    return plan.model_copy(
        update={
            "steps": steps,
            "rationale": plan.rationale + ";goal_contract",
            "read_contract_applied": True,
            "read_contract_mode": mode,
        }
    )


_WRITE_GOALS = {
    G.CANCEL: "cancel_order",
    G.REFUND_REQUEST: "create_refund_request",
    G.RETURN_REQUEST: "create_return_request",
}


def exclude_restricted_writes(
    plan: AgentPlan, goals: Sequence[TaskGoal], registry: ToolRegistry
) -> AgentPlan:
    """A negative or conditional goal can restrict a write, never authorize one."""
    barred = {
        _WRITE_GOALS[goal.kind] for goal in goals if goal.negated and goal.kind in _WRITE_GOALS
    }
    if any(goal.conditions and goal.operation != "read" for goal in goals):
        barred.update(tool.name for tool in registry.all() if tool.risk in WRITE_RISKS)
    if not barred:
        return plan
    return plan.model_copy(
        update={"steps": [step for step in plan.steps if step.tool_name not in barred]}
    )


_LIST_FIELDS: dict[str, dict[str, type]] = {
    "items": {
        "sku": str,
        "name": str,
        "quantity": int,
        "unit_price_cents": int,
        "customized": bool,
    },
    "events": {"status": str, "at": str},
    "refunds": {"refund_id": str, "status": str, "amount_cents": int},
    "chunks": {"content": str},
}


def _valid_field(field: str, value: object) -> bool:
    if field in _LIST_FIELDS:
        return (
            isinstance(value, list)
            and (field != "chunks" or bool(value))
            and all(
                isinstance(row, dict)
                and all(type(row.get(key)) is kind for key, kind in _LIST_FIELDS[field].items())
                for row in value
            )
        )
    if field in {"total_cents", "price_cents", "inventory"}:
        return type(value) is int and value >= 0
    if field == "status":
        return isinstance(value, str) and value in {status.value for status in OrderStatus}
    if field == "paid_at":
        if value is None:
            return True
        if not isinstance(value, str) or "T" not in value:
            return False
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return False
        return True
    if field == "tracking_no" and value is None:
        return True
    return isinstance(value, str) and bool(value.strip())


def observed_goal(goal: TaskGoal, arguments: dict, result: ToolResult) -> bool:
    """A capability alone does not count. Check a matching successful actual result."""
    if goal.negated or not goal.fields or not result.success or result.truncated:
        return False
    capability = CAPABILITIES.get(result.name)
    if (
        capability is None
        or goal.kind not in capability.goals
        or not set(goal.fields).issubset(goal_read_fields(goal.kind))
    ):
        return False
    expected = goal.request_text if goal.kind == G.POLICY else goal.entity_id
    if not expected or arguments.get(capability.argument) != expected:
        return False
    if capability.returned_entity and result.output.get(capability.returned_entity) != expected:
        return False
    return all(_observed_field(field, result.output) for field in goal.fields)


def _observed_field(field: str, data: dict) -> bool:
    if field == "items.customized":
        items = data.get("items")
        return isinstance(items, list) and all(
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and type(item.get("customized")) is bool
            for item in items
        )
    return field in data and _valid_field(field, data[field])
