"""Request goals and optional hints returned by the existing intent call."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntitySource = Literal["none", "current_user", "session_user", "session_summary_user_entity"]
EntityType = Literal["order", "product", "none"]
EntityScope = Literal["local", "distributive", "request", "context", "none"]
SignalCategory = Literal["action", "field", "constraint", "dependency", "background", "unresolved"]


class GoalKind(str, Enum):
    ORDER_STATUS = "order_status"
    ORDER_PAYMENT = "order_payment"
    ORDER_AMOUNT = "order_amount"
    ORDER_ITEMS = "order_items"
    SHIPMENT = "shipment"
    TRACKING_NUMBER = "tracking_number"
    REFUND_STATUS = "refund_status"
    INVENTORY = "inventory"
    PRODUCT_DETAIL = "product_detail"
    PRODUCT_PRICE = "product_price"
    POLICY = "policy"
    CANCEL = "cancel"
    RETURN_REQUEST = "return_request"
    REFUND_REQUEST = "refund_request"
    UNKNOWN = "unknown"


GOAL_FIELDS: dict[GoalKind, tuple[str, ...]] = {
    GoalKind.ORDER_STATUS: ("status",),
    GoalKind.ORDER_PAYMENT: ("paid_at",),
    GoalKind.ORDER_AMOUNT: ("total_cents",),
    GoalKind.ORDER_ITEMS: ("items",),
    GoalKind.SHIPMENT: ("events",),
    GoalKind.TRACKING_NUMBER: ("tracking_no",),
    GoalKind.REFUND_STATUS: ("refunds",),
    GoalKind.INVENTORY: ("inventory",),
    GoalKind.PRODUCT_DETAIL: ("name", "description"),
    GoalKind.PRODUCT_PRICE: ("price_cents",),
    GoalKind.POLICY: ("chunks",),
    GoalKind.CANCEL: ("status",),
    GoalKind.RETURN_REQUEST: ("return_id",),
    GoalKind.REFUND_REQUEST: ("refund_id",),
}


def goal_read_fields(kind: GoalKind) -> tuple[str, ...]:
    fields = GOAL_FIELDS.get(kind, ())
    return (*fields, "items.customized") if kind == GoalKind.ORDER_ITEMS else fields


class GoalSignal(BaseModel):
    kind: GoalKind = GoalKind.UNKNOWN
    quote: str = Field(min_length=2, max_length=240)
    category: SignalCategory = "action"
    fields: tuple[str, ...] = Field(default=(), max_length=8)
    operation: Literal["read", "write", "unknown"] = "unknown"
    independent: bool = False
    negated: bool = False


class SkillHint(BaseModel):
    """A candidate from the existing Intent response. Its quotes must be grounded."""

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    quote: str = Field(min_length=2, max_length=320)
    reason_quote: str | None = Field(default=None, min_length=1, max_length=200)
    needs_reference: bool = False


class DependencyHint(BaseModel):
    condition_quote: str = Field(min_length=2, max_length=160)
    action_quote: str = Field(min_length=2, max_length=240)


class VerifiedDependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_quote: str
    action_quote: str
    prerequisite_order_id: str
    predicate: Literal["is_paid"] = "is_paid"


class TaskGoal(BaseModel):
    """A current task with an independently sourced entity and requested evidence."""

    model_config = ConfigDict(frozen=True)

    kind: GoalKind
    request_text: str
    entity_type: EntityType = "none"
    entity_id: str | None = None
    entity_source: EntitySource = "none"
    entity_scope: EntityScope = "none"
    fields: tuple[str, ...] = ()
    operation: Literal["read", "write", "unknown"] = "read"
    negated: bool = False
    constraints: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    verified_dependency: VerifiedDependency | None = None
    clarification: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()
    independent: bool = False
