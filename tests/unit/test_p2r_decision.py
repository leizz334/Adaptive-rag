"""Generic R3 regressions: evidence capabilities, grounding and bounded reads."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.agents.nodes.executor as execution
from app.agents.nodes.planner import Planner, skill_to_plan
from app.config.settings import Settings
from app.core.enums import ToolRisk
from app.core.exceptions import InvalidRequestError, ToolExecutionError
from app.observability.execution import capture_tools
from app.providers.base import LLMResponse
from app.providers.fake import OfflineLLMProvider
from app.schemas.agent import AgentPlan, PlanStep, ToolResult
from app.tools.base import Tool
from app.tools.order_tools import OrderIdInput
from app.tools.registry import ToolRegistry

TRACKING = {"name": "order_tracking", "tools": ["get_order", "track_shipment"]}


class Observation(Tool):
    input_model = OrderIdInput
    description = "Synthetic current business observation"

    def __init__(self, name, *, store=None, risk=ToolRisk.READ, failure=None):
        self.name, self.risk, self.failure = name, risk, failure
        self.store = store if store is not None else {"status": "paid"}
        self.calls = 0

    async def execute(self, parsed, context):
        self.calls += 1
        if self.failure:
            raise self.failure
        if self.risk == ToolRisk.WRITE:
            self.store["status"] = "cancelled"
        return ToolResult(name=self.name, success=True, output=dict(self.store), risk=self.risk)


def registry(*tools):
    value = ToolRegistry()
    for tool in tools or [
        Observation(name) for name in ("get_order", "track_shipment", "get_order_items")
    ]:
        value.register(tool)
    return value


def names(plan):
    return [step.tool_name for step in plan.steps]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("麻烦顺手核实一下 ORD24680 目前订单的状态，谢谢", ["get_order"]),
        ("我想复核 ORD24680 已经支付的金额，请查当前记录", ["get_order"]),
        ("我现在只想知道 ORD24680 快递走到哪里了，再查一下轨迹", ["track_shipment"]),
        ("核对 ORD24680 订单金额，并展示运输的历史节点", ["get_order", "track_shipment"]),
        ("查看 ORD24680 的商品明细和数量", ["get_order_items"]),
    ],
)
def test_default_skill_selects_evidence_capabilities_without_whole_query_templates(query, expected):
    assert names(skill_to_plan(TRACKING, query, registry())) == expected


def test_transport_history_never_loses_shipment_capability():
    query = "查订单 ORD24680 的运输状态和历史节点"
    assert "track_shipment" in names(skill_to_plan(TRACKING, query, registry()))


def test_default_skill_expands_current_explicit_targets_without_arbitrary_selection():
    plan = skill_to_plan(TRACKING, "分别核对 ORD24680 和 ORD13579 的订单状态", registry())
    assert [(step.tool_name, step.arguments) for step in plan.steps] == [
        ("get_order", {"order_id": "ORD24680"}),
        ("get_order", {"order_id": "ORD13579"}),
    ]


async def test_raw_shipment_goal_is_separate_from_entity_status_hint():
    planner = Planner(OfflineLLMProvider(), registry())
    raw = "再查它的快递轨迹"
    plan = await planner.create_plan(
        raw + "（会话指代：订单 ORD24680，状态需实时查询）",
        "logistics",
        "",
        raw_query=raw,
        order_ids=("ORD24680",),
    )
    assert names(plan) == ["track_shipment"]
    assert plan.steps[0].arguments == {"order_id": "ORD24680"}


class ModelPlan:
    def __init__(self, steps):
        self.steps, self.calls = steps, []

    async def generate(self, messages, **kwargs):
        self.calls.append(messages)
        return LLMResponse(json.dumps({"steps": self.steps}))


def model_step(name, arguments):
    return {"step_id": 1, "goal": "current observation", "tool_name": name, "arguments": arguments}


@pytest.mark.parametrize("arguments", [{}, {"order_id": "订单号"}, {"order_id": "ORD13579"}])
async def test_model_order_arguments_must_satisfy_schema_and_current_bound_target(arguments):
    model = ModelPlan([model_step("get_order", arguments)])
    plan = await Planner(model, registry()).create_plan(
        "请核实 ORD24680 的订单状态", "order_inquiry", ""
    )
    assert model.calls
    assert names(plan) == ["get_order"]
    assert all(step.arguments.get("order_id") == "ORD24680" for step in plan.steps)
    for step in plan.steps:
        registry().get(step.tool_name).input_model.model_validate(step.arguments)


async def test_absent_target_clarifies_instead_of_dispatching_empty_arguments():
    model = ModelPlan([model_step("get_order", {})])
    plan = await Planner(model, registry()).create_plan(
        "核对那张订单的状态，我还没提供编号", "order_inquiry", ""
    )
    assert plan.steps == []
    assert "clarification" in plan.rationale


async def test_model_remains_primary_for_unrecognized_evidence_goal_and_catalog_has_schema():
    model = ModelPlan([model_step("get_order", {"order_id": "ORD24680"})])
    planner = Planner(model, registry())
    plan = await planner.create_plan("检查 ORD24680 的异常原因", "order_inquiry", "")
    assert names(plan) == ["get_order"]
    assert len(model.calls) == 1
    catalog = planner._tool_catalog()
    assert '"order_id"' in catalog and '"required"' in catalog


def step(name, index, order_id="ORD24680"):
    return PlanStep(
        step_id=index,
        goal="observe current facts",
        tool_name=name,
        arguments={"order_id": order_id},
    )


async def execute(monkeypatch, tools, steps, *, confirmation=None):
    monkeypatch.setattr(execution, "get_db_session", lambda: object())
    monkeypatch.setattr(
        execution,
        "IdempotencyRepository",
        lambda db: SimpleNamespace(
            get_if_matches=AsyncMock(return_value=None),
            put=AsyncMock(),
        ),
    )
    return await execution.executor_node(
        {
            "plan": AgentPlan(steps=steps),
            "user_id": "synthetic-user",
            "session_id": "synthetic-session",
            "trace_id": "synthetic-trace",
            "user_query": "核对当前业务记录",
            "confirm_action_id": confirmation,
        },
        registry=registry(*tools),
        settings=Settings(_env_file=None),
    )


async def test_exact_same_turn_read_is_dispatched_once_but_next_turn_is_fresh(monkeypatch):
    read = Observation("get_order")
    repeated = [step("get_order", 1), step("get_order", 2)]
    first = await execute(monkeypatch, [read], repeated)
    assert read.calls == 1
    assert len(first["tool_results"]) == 1
    await execute(monkeypatch, [read], repeated)
    assert read.calls == 2


async def test_distinct_targets_are_not_deduplicated(monkeypatch):
    read = Observation("get_order")
    await execute(monkeypatch, [read], [step("get_order", 1), step("get_order", 2, "ORD13579")])
    assert read.calls == 2


async def test_read_after_write_is_fresh_and_write_permission_is_preserved(monkeypatch):
    store = {"status": "paid"}
    read, write = (
        Observation("get_order", store=store),
        Observation("cancel_order", store=store, risk=ToolRisk.WRITE),
    )
    value = await execute(
        monkeypatch,
        [read, write],
        [step("get_order", 1), step("cancel_order", 2), step("get_order", 3)],
        confirmation="synthetic-confirmation",
    )
    assert read.calls == 2 and write.calls == 1
    assert [result.output["status"] for result in value["tool_results"]] == [
        "paid",
        "cancelled",
        "cancelled",
    ]
    denied = Observation("cancel_order", risk=ToolRisk.WRITE)
    result = await execute(monkeypatch, [denied], [step("cancel_order", 1)])
    assert denied.calls == 0 and not result["tool_results"][0].success


async def test_deterministic_rejection_is_not_retried_by_duplicate_or_fallback(monkeypatch):
    rejected = Observation(
        "track_shipment", failure=InvalidRequestError("synthetic owner rejection")
    )
    fallback = Observation("get_order")
    await execute(
        monkeypatch, [rejected, fallback], [step("track_shipment", 1), step("track_shipment", 2)]
    )
    assert rejected.calls == 1 and fallback.calls == 0


async def test_transient_fallback_success_counts_as_this_turn_observation(monkeypatch):
    transient = Observation(
        "track_shipment", failure=ToolExecutionError("synthetic temporary outage")
    )
    fallback = Observation("get_order")
    await execute(
        monkeypatch, [transient, fallback], [step("track_shipment", 1), step("get_order", 2)]
    )
    assert transient.calls == 1 and fallback.calls == 1


@pytest.mark.parametrize(
    "query",
    [
        "请核实 ORD86420 的支付状态，并列出包裹每次中转的时间和地点",
        "订单 ORD86420 的状态，以及承运商最后一次装卸记录",
    ],
)
async def test_real_model_keeps_capabilities_for_unrecognized_additional_obligations(query):
    model = ModelPlan(
        [model_step(name, {"order_id": "ORD86420"}) for name in ("get_order", "track_shipment")]
    )
    plan = await Planner(model, registry()).create_plan(query, "order_inquiry", "")
    assert names(plan) == ["get_order", "track_shipment"]
    assert "- track_shipment:" in model.calls[0][0]["content"]


async def test_planner_preserves_bounded_repeated_steps_until_actual_result_is_known():
    model = ModelPlan([model_step("get_order", {"order_id": "ORD24680"})] * 2)
    plan = await Planner(model, registry()).create_plan("订单 ORD24680 状态", "order_inquiry", "")
    assert names(plan) == ["get_order", "get_order"]


async def test_transient_failed_read_does_not_suppress_next_bounded_planned_attempt(monkeypatch):
    class Flaky(Observation):
        async def execute(self, parsed, context):
            self.calls += 1
            if self.calls == 1:
                raise ToolExecutionError("temporary backend failure")
            return ToolResult(name=self.name, success=True, output={"status": "paid"})

    read = Flaky("get_order")
    result = await execute(monkeypatch, [read], [step("get_order", 1), step("get_order", 2)])
    assert read.calls == 2
    assert result["tool_results"][-1].success


async def test_owner_not_found_stops_other_reads_only_for_same_entity_this_turn(monkeypatch):
    class TargetRead(Observation):
        def __init__(self):
            super().__init__("track_shipment")
            self.targets = []

        async def execute(self, parsed, context):
            self.targets.append(parsed.order_id)
            return await super().execute(parsed, context)

    denied = Observation("get_order", failure=InvalidRequestError("order not found: ORD24680"))
    tracking = TargetRead()
    await execute(
        monkeypatch,
        [denied, tracking],
        [
            step("get_order", 1),
            step("track_shipment", 2),
            step("track_shipment", 3, "ORD13579"),
        ],
    )
    assert denied.calls == 1 and tracking.targets == ["ORD13579"]
    await execute(monkeypatch, [tracking], [step("track_shipment", 1)])
    assert tracking.targets == ["ORD13579", "ORD24680"]


async def test_generic_invalid_request_does_not_block_other_read_capabilities(monkeypatch):
    rejected = Observation("get_order", failure=InvalidRequestError("unsupported order view"))
    tracking = Observation("track_shipment")
    await execute(
        monkeypatch, [rejected, tracking], [step("get_order", 1), step("track_shipment", 2)]
    )
    assert rejected.calls == tracking.calls == 1


async def test_malformed_entity_arguments_still_reach_schema_rejection_without_guard_crash(
    monkeypatch,
):
    read = Observation("get_order")
    malformed = step("get_order", 1).model_copy(
        update={"arguments": {"order_id": {"untrusted": "value"}}}
    )
    result = await execute(monkeypatch, [read], [malformed, malformed])
    assert read.calls == 0
    assert len(result["tool_results"]) == 1 and not result["tool_results"][0].success


async def test_repeated_transient_primary_reuses_successful_fallback_only_within_turn(monkeypatch):
    primary = Observation("track_shipment", failure=ToolExecutionError("temporary tracking outage"))
    fallback = Observation("get_order")
    steps = [step("track_shipment", 1), step("track_shipment", 2)]
    with capture_tools() as events:
        await execute(monkeypatch, [primary, fallback], steps)
    assert primary.calls == 2 and fallback.calls == 1
    assert [event["name"] for event in events].count("get_order") == 1
    await execute(monkeypatch, [primary, fallback], steps)
    assert primary.calls == 4 and fallback.calls == 2


async def test_write_attempt_invalidates_successful_fallback_observation(monkeypatch):
    store = {"status": "paid"}
    primary = Observation("track_shipment", failure=ToolExecutionError("temporary tracking outage"))
    fallback = Observation("get_order", store=store)
    write = Observation("cancel_order", store=store, risk=ToolRisk.WRITE)
    result = await execute(
        monkeypatch,
        [primary, fallback, write],
        [
            step("track_shipment", 1),
            step("cancel_order", 2),
            step("track_shipment", 3),
        ],
        confirmation="synthetic-confirmation",
    )
    assert primary.calls == 2 and fallback.calls == 2
    assert [item.output["status"] for item in result["tool_results"]] == [
        "paid",
        "cancelled",
        "cancelled",
    ]
