import json
from functools import partial

import pytest

from app.agents.goals import resolve_goals
from app.agents.nodes.planner import Planner
from app.agents.planning import select_planning_strategy
from app.providers.base import LLMResponse
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.order_tools import GetOrderTool
from app.tools.registry import ToolRegistry


def _registry():
    registry = ToolRegistry()
    registry.register(GetOrderTool())
    registry.register(TrackShipmentTool())
    return registry


def _call(name, arguments):
    return {
        "id": "call-demo",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class Provider:
    def __init__(self, calls):
        self.calls = calls
        self.requests = []

    async def generate(self, messages, **options):
        self.requests.append((messages, options))
        if options.get("tools"):
            return LLMResponse("", tool_calls=self.calls)
        return LLMResponse(
            json.dumps(
                {
                    "steps": [
                        {
                            "step_id": 1,
                            "goal": "read",
                            "tool_name": "get_order",
                            "arguments": {"order_id": "ORD10001"},
                        }
                    ]
                }
            )
        )


async def test_native_plan_preserves_order_validates_shape_and_shares_candidate_filter():
    provider = Provider(
        [
            _call("get_order", '{"order_id":"ORD10001"}'),
            _call("get_order", '{"order_id":"ORD10002","order_id":"ORD10003"}'),
            _call("cancel_order", '{"order_id":"ORD10001"}'),
            _call("track_shipment", '{"order_id":"ORD10002"}'),
        ]
    )
    planner = Planner(provider, _registry(), mode="function_calling")
    plan = await planner._create_plan(
        "两笔的状态和物流", "order_inquiry", "", contract_tools={"get_order", "track_shipment"}
    )
    assert [(s.step_id, s.tool_name, s.arguments) for s in plan.steps] == [
        (1, "get_order", {"order_id": "ORD10001"}),
        (3, "track_shipment", {"order_id": "ORD10002"}),
    ]
    assert len(provider.requests) == 1
    _, kwargs = provider.requests[0]
    assert kwargs["tool_choice"] == "auto" and "response_format" not in kwargs
    assert [tool["function"]["name"] for tool in kwargs["tools"]] == ["get_order", "track_shipment"]


async def test_json_default_uses_existing_prompt_and_no_native_schema():
    provider = Provider([])
    plan = await Planner(provider, _registry())._create_plan(
        "ORD10001 状态", "order_inquiry", "", contract_tools={"get_order"}
    )
    assert plan.steps[0].tool_name == "get_order"
    assert provider.requests[0][1]["response_format"] == {"type": "json_object"}
    assert "tools" not in provider.requests[0][1]


def test_strict_beta_profiles_keep_supported_pattern_without_mutating_registry():
    from app.agents.dynamic_planning import strict_tool_definitions

    schema = GetOrderTool().openai_schema()
    (strict_schema,) = strict_tool_definitions([schema])
    definition = strict_schema["function"]
    assert definition["strict"] is True and "strict" not in schema["function"]
    params = definition["parameters"]
    assert params["additionalProperties"] is False
    assert params["required"] == ["order_id"] and "pattern" in params["properties"]["order_id"]
    assert "maxLength" not in params["properties"]["order_id"]


def test_strict_beta_rejects_optional_fields_without_silently_changing_required_arguments():
    from app.agents.dynamic_planning import strict_tool_definitions
    from app.tools.product_tools import RecommendProductsTool

    with pytest.raises(ValueError, match="optional"):
        strict_tool_definitions([RecommendProductsTool().openai_schema()])


async def test_native_setting_preserves_direct_and_shared_contract_repair(monkeypatch):
    query = "查一下 ORD10001 的订单状态"
    goals = resolve_goals(query)
    provider = Provider([_call("get_order", '{"order_id":"ORD10002"}')])
    planner = Planner(provider, _registry(), mode="function_calling")
    direct = await planner.create_plan(query, "order_inquiry", "", task_goals=goals)
    assert direct.planning_strategy == "direct" and not provider.requests
    monkeypatch.setattr(
        "app.agents.nodes.planner.select_planning_strategy",
        partial(select_planning_strategy, direct_enabled=False),
    )
    dynamic = await planner.create_plan(query, "order_inquiry", "", task_goals=goals)
    assert dynamic.planning_strategy == "dynamic" and len(provider.requests) == 1
    assert [step.arguments for step in dynamic.steps] == [{"order_id": "ORD10001"}]


def test_malformed_native_container_and_entries_are_typed_decode_errors():
    from app.agents.dynamic_planning import decode_native_plan

    assert decode_native_plan({"unexpected": True}).issues == ("call_schema",)
    decoded = decode_native_plan([None, _call("get_order", "{}")])
    assert decoded.issues == ("call_schema",)
    assert [s.tool_name for s in decoded.plan.steps] == ["get_order"]


async def test_truncated_response_does_not_use_the_native_proposal():
    class Truncated(Provider):
        async def generate(self, messages, **options):
            result = await super().generate(messages, **options)
            result.finish_reason = "length"
            return result

    provider = Truncated([_call("get_order", '{"order_id":"ORD10002"}')])
    planner = Planner(provider, _registry(), mode="function_calling")
    plan = await planner._create_plan(
        "查 ORD10001 的订单状态", "order_inquiry", "", contract_tools={"get_order"}
    )
    assert provider.requests
    assert all(s.arguments.get("order_id") != "ORD10002" for s in plan.steps)
