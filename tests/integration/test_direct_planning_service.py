from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder, safe_metadata
from app.schemas.chat import ChatRequest
from app.tools.logistics_tools import TrackShipmentTool
from eval.environment import BusinessEnvironment


async def test_two_explicit_order_reads_can_pass_the_existing_context_gate():
    async with BusinessEnvironment(memory_mode="M2") as env:
        with capture_tools() as events:
            response = await env.service.chat(
                ChatRequest(
                    user_id="u_demo", message="查 ORD10001 的订单状态。再查 ORD10002 的退款进度。"
                ),
                trace_id="p3-distinct-orders",
            )
    assert response.strategy == "agent" and response.pending_action is None
    assert [(e["name"], e["arguments"].get("order_id"), e["success"]) for e in events] == [
        ("get_order", "ORD10001", True),
        ("get_refund_status", "ORD10002", True),
    ]


async def test_alternative_ordernumbers_are_not_treated_as_a_list():
    async with BusinessEnvironment(memory_mode="M2") as env:
        with capture_tools() as events:
            response = await env.service.chat(
                ChatRequest(user_id="u_demo", message="请查 ORD10001 或 ORD10002 的订单状态。"),
                trace_id="p3-alternative-orders",
            )
    assert not events and "请明确" in response.answer and response.pending_action is None


async def test_direct_tool_failure_stays_bounded_and_traces_the_missing_fact(monkeypatch):
    async def broken(self, parsed, context):
        raise RuntimeError("synthetic tool failure")

    monkeypatch.setattr(TrackShipmentTool, "execute", broken)
    recorded = []
    async with BusinessEnvironment(memory_mode="M2") as env:
        env.service._tracer = TraceRecorder(enabled=True, sink=recorded.extend)
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(user_id="u_demo", message="查 ORD10001 的物流轨迹。"),
                trace_id="p3-traced-failure",
            )
    assert [(e["name"], e["success"]) for e in events] == [("track_shipment", False)]
    (strategy,) = [s.metadata for s in recorded if s.name == "planner.strategy"]
    (execution,) = [s.metadata for s in recorded if s.name == "planner.execution"]
    assert strategy["planning_strategy"] == "direct" and strategy["planner_llm_calls"] == 0
    assert strategy["planned_tools"] == ["track_shipment"]
    assert execution["missing_evidence_kinds"] == ["shipment"]
    assert execution["successful_tool_count"] == execution["observed_goal_count"] == 0
    assert "ORD10001" not in repr(recorded)
    assert safe_metadata(
        {
            "planning_reason": "hidden-identifier",
            "planned_tools": ["hidden-identifier", "get_order"],
        }
    ) == {"planned_tools": ["get_order"]}
