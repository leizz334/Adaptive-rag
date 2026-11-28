from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.agents.goal_answers import bounded_read_answer
from app.agents.nodes.executor import executor_node
from app.agents.nodes.generate import generate_node
from app.agents.workflow_execution import workflow_gate
from app.config.settings import Settings
from app.core.request_scope import request_session
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.providers.fake import OfflineLLMProvider
from app.repositories.db import create_engine, create_session_factory, init_schema
from app.repositories.models import AuditLogRow, OrderRow, ReturnRow
from app.schemas.agent import AgentPlan, PlanStep, ToolResult
from app.schemas.goals import GoalKind, TaskGoal
from app.services.seed import seed_demo_data
from app.tools.aftersale_tools import CancelOrderTool, CreateReturnRequestTool
from app.tools.order_tools import GetOrderItemsTool, GetOrderTool
from app.tools.registry import ToolRegistry


def _step(step_id, tool_name, order_id, **fields):
    return {
        "step_id": step_id,
        "goal": "Verify a registered business read",
        "tool_name": tool_name,
        "arguments": {"order_id": order_id},
        **fields,
    }


def _plan(steps, **fields):
    return AgentPlan.model_validate(
        {"skill_name": "test-workflow", "skill_mode": "workflow", "steps": steps, **fields}
    )


def _items_goal(order_id):
    return TaskGoal(
        kind=GoalKind.ORDER_ITEMS,
        request_text="核对商品明细",
        entity_type="order",
        entity_id=order_id,
        entity_source="current_user",
        fields=("items",),
    )


def _write_goal(tool_name, order_id, **fields):
    kind = GoalKind.CANCEL if tool_name == "cancel_order" else GoalKind.RETURN_REQUEST
    return TaskGoal(
        kind=kind,
        request_text="提交操作申请",
        entity_type="order",
        entity_id=order_id,
        entity_source="current_user",
        operation="write",
        **fields,
    )


@asynccontextmanager
async def _environment():
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    engine = create_engine(settings)
    try:
        await init_schema(engine)
        factory = create_session_factory(engine)
        async with factory() as session:
            await seed_demo_data(session)
            await session.commit()
        registry = ToolRegistry()
        for tool in (
            CancelOrderTool(),
            CreateReturnRequestTool(),
            GetOrderTool(),
            GetOrderItemsTool(),
        ):
            registry.register(tool)
        yield SimpleNamespace(factory=factory, registry=registry, settings=settings)
    finally:
        await engine.dispose()


async def _snapshot(env):
    async with env.factory() as session:
        orders = (await session.execute(select(OrderRow.order_id, OrderRow.status))).all()
        returns = await session.scalar(select(func.count()).select_from(ReturnRow))
        audit = await session.scalar(select(func.count()).select_from(AuditLogRow))
    return sorted(orders), returns, audit


async def _execute(env, plan, *, user_id="u_demo", goals=(), trace_sink=None):
    state = {
        "plan": plan,
        "user_id": user_id,
        "session_id": "workflow-test",
        "trace_id": "workflow-test",
        "user_query": "如已付款再查商品明细",
        "task_goals": list(goals),
    }
    recorder = TraceRecorder(enabled=trace_sink is not None, sink=trace_sink)
    with capture_tools() as events, recorder.turn(trace_id="workflow-test"):
        async with request_session(env.factory):
            result = await executor_node(state, registry=env.registry, settings=env.settings)
    return {**state, **result}, events


@pytest.mark.parametrize(
    ("order_id", "order_status", "target_status", "outcome"),
    [
        ("ORD10001", "shipped", "executed", "降噪耳机 Pro"),
        ("ORD10001", "created", "condition_false", "条件不成立"),
        ("ORD10001", "shipped_no_payment_record", "condition_unknown", "未取得足够证据"),
        ("ORD99999", None, "prerequisite_failed", "前置查询失败"),
    ],
)
async def test_registered_payment_condition_keeps_independent_result(
    order_id, order_status, target_status, outcome
):
    async with _environment() as env:
        if order_status in {"created", "shipped_no_payment_record"}:
            async with env.factory() as session:
                row = await session.get(OrderRow, order_id)
                row.status = "created" if order_status == "created" else "shipped"
                row.paid_at = None
                await session.commit()
        plan = _plan(
            [
                _step(1, "get_order", order_id),
                _step(
                    2,
                    "get_order_items",
                    order_id,
                    depends_on=(1,),
                    condition={"source_step_id": 1},
                ),
                _step(3, "get_order_items", "ORD10003"),
            ]
        )
        state, events = await _execute(
            env, plan, goals=(_items_goal(order_id), _items_goal("ORD10003"))
        )
        assert state["workflow_step_statuses"][2] == target_status
        assert state["tool_result_steps"] == ([1, 2, 3] if target_status == "executed" else [1, 3])
        assert sum(e["name"] == "get_order_items" for e in events) == (
            2 if target_status == "executed" else 1
        )
        assert all(e["name"] != "search_knowledge" for e in events)
        answer = bounded_read_answer(state)
        assert answer and outcome in answer and "纯棉T恤" in answer


@pytest.mark.parametrize(
    "steps",
    [
        [_step(1, "get_order", "ORD10001"), _step(1, "get_order_items", "ORD10001")],
        [_step(1, "get_order", "ORD10001", depends_on=(2,)), _step(2, "get_order", "ORD10001")],
        [
            _step(1, "get_order", "ORD10001", depends_on=(2,)),
            _step(2, "get_order", "ORD10001", depends_on=(1,)),
        ],
        [_step(1, "get_order", "ORD10001", depends_on=(99,))],
        [_step(1, "cancel_order", "ORD10001")],
        [_step(1, "unregistered_call", "ORD10001")],
        [_step(1, "get_order", "ORD10001", arguments={"sku": "SKU-TEE"})],
        [_step(step_id, "get_order", "ORD10001") for step_id in range(1, 8)],
        [
            _step(1, "get_order_items", "ORD10001"),
            _step(2, "get_order", "ORD10001", depends_on=(1,), condition={"source_step_id": 1}),
        ],
    ],
)
async def test_invalid_workflow_is_rejected_before_any_call(steps):
    async with _environment() as env:
        state, events = await _execute(env, _plan(steps))
        assert state["workflow_error"] == "invalid_plan"
        assert state["tool_results"] == []
        assert not events


@pytest.mark.parametrize(
    ("tool_name", "order_id", "user_id", "expected_status"),
    [
        ("cancel_order", "ORD10003", "u_demo", "ready"),
        ("cancel_order", "ORD10001", "u_demo", "ineligible"),
        ("cancel_order", "ORD10003", "other", "failed"),
        ("create_return_request", "ORD10001", "u_demo", "ready"),
    ],
)
async def test_workflow_write_is_only_proposed_after_visible_order_evidence(
    tool_name, order_id, user_id, expected_status
):
    async with _environment() as env:
        before = await _snapshot(env)
        arguments = {"order_id": order_id}
        if tool_name == "create_return_request":
            arguments["reason"] = "尺寸不合适"
        plan = _plan(
            [_step(1, "get_order", order_id)],
            workflow_action={"tool_name": tool_name, "arguments": arguments, "source_step_id": 1},
        )
        state, events = await _execute(
            env, plan, user_id=user_id, goals=(_write_goal(tool_name, order_id),)
        )
        assert state["workflow_action_status"] == expected_status
        assert [e["name"] for e in events] == ["get_order"]
        if expected_status == "ready":
            assert state["pending_action"].tool_name == tool_name
            assert state["pending_action"].arguments == arguments
        else:
            assert state["pending_action"] is None
            assert bounded_read_answer(state)
        assert await _snapshot(env) == before


async def test_preflight_cannot_authorize_write_to_another_order():
    async with _environment() as env:
        plan = _plan(
            [_step(1, "get_order", "ORD10001")],
            workflow_action={
                "tool_name": "cancel_order",
                "arguments": {"order_id": "ORD10003"},
                "source_step_id": 1,
            },
        )
        state, events = await _execute(env, plan)
        assert state["workflow_error"] == "invalid_plan"
        assert not events


async def test_preflight_cannot_authorize_conditional_write():
    async with _environment() as env:
        plan = _plan(
            [_step(1, "get_order", "ORD10003")],
            workflow_action={
                "tool_name": "cancel_order",
                "arguments": {"order_id": "ORD10003"},
                "source_step_id": 1,
            },
        )
        state, events = await _execute(
            env, plan, goals=(_write_goal("cancel_order", "ORD10003", conditions=("待审批",)),)
        )
        assert state["workflow_error"] == "invalid_plan"
        assert not events


@pytest.mark.parametrize(
    ("changes", "truncated"),
    [
        ({"order_id": "ORD10003"}, False),
        ({"user_id": "other"}, False),
        ({"paid_at": "invalid date"}, False),
        ({"paid_at": "2026-11-27"}, False),
        ({"status": "created"}, False),
        ({"fallback_from": "track_shipment"}, False),
        ({}, True),
    ],
)
def test_untrustworthy_order_result_cannot_prove_payment(changes, truncated):
    step = PlanStep.model_validate(
        _step(2, "get_order_items", "ORD10001", depends_on=(1,), condition={"source_step_id": 1})
    )
    source = ToolResult(
        name="get_order",
        success=True,
        truncated=truncated,
        output={
            "order_id": "ORD10001",
            "user_id": "u_demo",
            "status": "shipped",
            "paid_at": "2026-11-27T09:30:00",
            **changes,
        },
    )
    assert workflow_gate(step, {1: "executed"}, {1: source}, "u_demo") == (
        "condition_unknown",
        "unknown",
    )


async def test_workflow_pending_answer_keeps_independent_evidence_and_bounded_trace():
    async with _environment() as env:
        plan = _plan(
            [_step(1, "get_order", "ORD10003"), _step(2, "get_order_items", "ORD10001")],
            workflow_action={
                "tool_name": "cancel_order",
                "arguments": {"order_id": "ORD10003"},
                "source_step_id": 1,
            },
        )
        traces = []
        state, _ = await _execute(
            env,
            plan,
            goals=(_write_goal("cancel_order", "ORD10003"), _items_goal("ORD10001")),
            trace_sink=traces.extend,
        )
        generated = await generate_node(state, OfflineLLMProvider())
        assert "确认后将取消订单 ORD10003" in generated["final_answer"]
        assert "降噪耳机 Pro" in generated["final_answer"]
        steps = [trace for trace in traces if trace.name == "skill.workflow.step"]
        assert [trace.metadata["workflow_step_id"] for trace in steps] == [1, 2]
        assert all(trace.metadata["workflow_step_status"] == "executed" for trace in steps)
        assert "ORD10001" not in str([trace.metadata for trace in traces])
        assert "ORD10003" not in str([trace.metadata for trace in traces])
