"""Source-bound records in the existing M2 session summary. Evidence is historical metadata."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.state import AgentState
from app.core.exceptions import GuardrailError
from app.guardrails.injection import detect_prompt_injection
from app.memory.context import user_orders
from app.repositories.models import MessageRow
from app.schemas.goals import GoalKind, TaskGoal, goal_read_fields

MAX_TASKS = 16
MAX_QUOTE = 640
SKU_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])SKU[-_][A-Za-z0-9_-]{1,28}(?![A-Za-z0-9_-])", re.I)
_TITLE = re.compile(r"[「『“\"]([^」』”\"\n]{2,64})[」』”\"]")


class RememberedGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: TaskGoal
    status: Literal["open", "completed", "awaiting_confirmation"]


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(max_length=48)
    fields: tuple[str, ...] = Field(max_length=8)
    at: datetime


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: int = Field(gt=0)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    order_ids: tuple[str, ...] = Field(default=(), max_length=8)
    product_skus: tuple[str, ...] = Field(default=(), max_length=8)
    product_name: str | None = Field(default=None, max_length=64)
    goals: tuple[RememberedGoal, ...] = Field(default=(), max_length=8)
    evidence: tuple[EvidenceReference, ...] = Field(default=(), max_length=8)
    pending_ref: str | None = Field(default=None, pattern=r"^[a-f0-9]{24}$")
    settled_task_id: int | None = Field(default=None, gt=0)
    protected: bool = False


@dataclass(frozen=True)
class TaskSource:
    record: TaskRecord
    text: str


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def safe_user_text(row: MessageRow) -> bool:
    if row.role != "user":
        return False
    try:
        detect_prompt_injection(row.content)
    except GuardrailError:
        return False
    return True


def _skus(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.upper() for match in SKU_PATTERN.findall(text)))[:8]


def _grounded_goal(goal: TaskGoal, text: str) -> bool:
    return (
        bool(goal.request_text.strip())
        and len(goal.request_text) <= MAX_QUOTE
        and goal.request_text.upper() in text.upper()
        and len(goal.constraints) <= 8
        and len(goal.conditions) <= 8
        and all(
            quote and len(quote) <= MAX_QUOTE and quote in text
            for quote in (*goal.constraints, *goal.conditions)
        )
        and (not goal.entity_id or goal.entity_id in {*user_orders(text), *_skus(text)})
    )


def restore_source(record: TaskRecord, row: MessageRow, ttl: int) -> TaskSource | None:
    created = row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC)
    if (
        row.id != record.message_id
        or not safe_user_text(row)
        or (datetime.now(UTC) - created).total_seconds() > ttl
        or _digest(row.content) != record.source_hash
        or tuple(user_orders(row.content)[:8]) != record.order_ids
        or _skus(row.content) != record.product_skus
        or (record.product_name is not None and record.product_name not in row.content)
        or any(not _grounded_goal(item.goal, row.content) for item in record.goals)
    ):
        return None
    return TaskSource(record, row.content)


def merge_records(*groups: Sequence[TaskRecord]) -> list[TaskRecord]:
    records = {task.message_id: task for group in groups for task in group}
    return sorted(records.values(), key=lambda task: task.message_id)[-MAX_TASKS:]


def task_record(row: MessageRow, state: AgentState | None = None) -> TaskRecord | None:
    if not safe_user_text(row) or (state and state.get("refused")):
        return None
    from app.agents.goal_answers import find_goal_observation
    from app.agents.goals import resolve_goals

    text = row.content
    orders, skus = tuple(user_orders(text)[:8]), _skus(text)
    plan = state.get("plan") if state else None
    results = state.get("tool_results", []) if state else []
    result_steps = state.get("tool_result_steps", []) if state else []
    pending = state.get("pending_action") if state else None
    available = (
        state.get("task_goals", []) if state else resolve_goals(text) if orders or skus else []
    )
    goals: list[RememberedGoal] = []
    evidence: list[EvidenceReference] = []
    for goal in available[:8]:
        if goal.kind == GoalKind.UNKNOWN or not _grounded_goal(goal, text):
            continue
        observation = (
            find_goal_observation(goal, plan, results, result_steps)
            if plan and goal.operation == "read"
            else None
        )
        status: Literal["open", "completed", "awaiting_confirmation"]
        status = "completed" if observation else "awaiting_confirmation" if pending else "open"
        goals.append(RememberedGoal(goal=goal, status=status))
        if observation:
            entry = EvidenceReference(
                tool=observation.name, fields=goal.fields, at=datetime.now(UTC)
            )
            if not any((item.tool, item.fields) == (entry.tool, entry.fields) for item in evidence):
                evidence.append(entry)
    product_name = None
    if plan:
        for step in plan.steps:
            name = step.arguments.get("query")
            if (
                step.tool_name == "search_products"
                and isinstance(name, str)
                and 2 <= len(name) <= 64
                and name in text
                and any(
                    result.name == step.tool_name
                    and result.success
                    and not result.truncated
                    and "fallback_from" not in result.output
                    and isinstance(products := result.output.get("products"), list)
                    and len(products) == 1
                    and isinstance(products[0], dict)
                    and name.casefold() in str(products[0].get("name", "")).casefold()
                    for step_id, result in zip(result_steps, results, strict=False)
                    if step_id == step.step_id
                )
            ):
                product_name = name
                break
    if product_name is None and (skus or any(g.goal.entity_type == "product" for g in goals)):
        if match := _TITLE.search(text):
            product_name = match[1]
    resumed = getattr(state.get("selected_context") if state else None, "resumed_from", None)
    settled = resumed if resumed and any(item.status == "completed" for item in goals) else None
    if not (orders or skus or product_name or goals or pending or settled):
        return None
    return TaskRecord(
        message_id=row.id,
        source_hash=_digest(text),
        order_ids=orders,
        product_skus=skus,
        product_name=product_name,
        goals=tuple(goals),
        evidence=tuple(evidence),
        pending_ref=_digest(pending.action_id)[:24] if pending else None,
        settled_task_id=settled,
        protected=any(
            goal.negated or goal.conditions or goal.constraints or goal.operation != "read"
            for goal in available
        ),
    )


def resumable_goal(item: RememberedGoal) -> bool:
    goal = item.goal
    return bool(
        goal.operation == "read"
        and goal.entity_type in {"order", "product"}
        and goal.fields
        and set(goal.fields).issubset(goal_read_fields(goal.kind))
        and not (goal.negated or goal.conditions or goal.unavailable_fields)
    )
