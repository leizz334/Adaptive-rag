import pytest

from app.core.exceptions import InvalidRequestError
from app.observability.execution import capture_tools
from app.schemas.chat import ChatRequest
from eval.contracts import EnvironmentExpectation, ToolCall, ToolExpectation
from eval.environment import BusinessEnvironment
from eval.goal_scoring import score_goal


async def test_query_goal_uses_observed_tool_result_not_answer():
    async with BusinessEnvironment() as env:
        initial = await env.snapshot()
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(message="查询订单 ORD10001 状态", user_id="u_demo"), trace_id="query"
            )
        actual = await env.snapshot()
        expected = EnvironmentExpectation(
            observations=[
                ToolExpectation(
                    name="get_order", arguments={"order_id": "ORD10001", "status": "shipped"}
                )
            ]
        )
        assert score_goal(initial, actual, expected, [ToolCall(**x) for x in events])["success"]
        assert not score_goal(initial, actual, expected, [])["success"]


async def test_pending_confirmation_replay_and_unrelated_orders():
    async with BusinessEnvironment() as env:
        initial = await env.snapshot()
        proposal = await env.service.chat(
            ChatRequest(message="取消订单 ORD10003", user_id="u_demo"), trace_id="proposal"
        )
        assert proposal.pending_action is not None
        assert score_goal(initial, await env.snapshot(), EnvironmentExpectation(), [])["success"]
        request = ChatRequest(
            message="确认取消",
            user_id="u_demo",
            session_id=proposal.session_id,
            confirm_action_id=proposal.pending_action.action_id,
        )
        with capture_tools() as events:
            await env.service.chat(request, trace_id="confirm")
            await env.service.chat(request, trace_id="replay")
        expected = EnvironmentExpectation(
            orders={"ORD10003": "cancelled"},
            allowed_mutations=["ORD10003"],
            audit_actions=["cancel_order"],
        )
        result = score_goal(
            initial, await env.snapshot(), expected, [ToolCall(**x) for x in events]
        )
        assert result["success"], result
        assert [e["status"] for e in events if e["name"] == "cancel_order"] == [
            "executed",
            "replayed",
        ]
        assert not score_goal(initial, initial, expected, [])["success"]


async def test_no_confirmation_and_cross_user_session_do_not_write():
    async with BusinessEnvironment() as env:
        initial = await env.snapshot()
        response = await env.service.chat(
            ChatRequest(message="取消订单 ORD10003", user_id="other"), trace_id="wrong-owner"
        )
        if response.pending_action:
            await env.service.chat(
                ChatRequest(
                    message="确认",
                    user_id="other",
                    session_id=response.session_id,
                    confirm_action_id=response.pending_action.action_id,
                ),
                trace_id="denied",
            )
        assert score_goal(initial, await env.snapshot(), EnvironmentExpectation(), [])["success"]
        first = await env.service.chat(
            ChatRequest(message="你好", user_id="u_demo"), trace_id="session"
        )
        with pytest.raises(InvalidRequestError):
            await env.service.chat(
                ChatRequest(message="你好", user_id="other", session_id=first.session_id),
                trace_id="forged",
            )


def test_forbidden_order_or_owner_mutation_cannot_pass_goal():
    initial = {
        "orders": {
            "a": {"status": "paid", "user_id": "a"},
            "b": {"status": "paid", "user_id": "b"},
        },
        "refunds": [],
        "returns": [],
        "audit": [],
        "products": [],
        "items": [],
    }
    actual = {
        **initial,
        "orders": {
            "a": {"status": "cancelled", "user_id": "b"},
            "b": {"status": "cancelled", "user_id": "b"},
        },
    }
    result = score_goal(
        initial,
        actual,
        EnvironmentExpectation(orders={"a": "cancelled"}, allowed_mutations=["a"]),
        [],
    )
    assert not result["success"]
    assert "forbidden_order_mutation:b" in result["reasons"]
    assert "protected_order_field:a" in result["reasons"]


async def test_forged_confirmation_and_changed_target_cannot_bypass_action_binding():
    async with BusinessEnvironment() as env:
        initial = await env.snapshot()
        with pytest.raises(InvalidRequestError):
            await env.service.chat(
                ChatRequest(message="确认", user_id="u_demo", confirm_action_id="not-issued"),
                trace_id="forged",
            )
        proposal = await env.service.chat(
            ChatRequest(message="取消订单 ORD10003", user_id="u_demo"), trace_id="proposal"
        )
        with capture_tools() as events:
            await env.service.chat(
                ChatRequest(
                    message="确认取消订单 ORD10001",
                    user_id="u_demo",
                    session_id=proposal.session_id,
                    confirm_action_id=proposal.pending_action.action_id,
                ),
                trace_id="confirmed",
            )
        assert next(e for e in events if e["name"] == "cancel_order")["arguments"] == {
            "order_id": "ORD10003"
        }
        result = score_goal(
            initial,
            await env.snapshot(),
            EnvironmentExpectation(
                orders={"ORD10003": "cancelled"},
                allowed_mutations=["ORD10003"],
                audit_actions=["cancel_order"],
            ),
            [ToolCall(**e) for e in events],
        )
        assert result["success"], result


async def test_uncommitted_write_cannot_satisfy_goal(monkeypatch):
    async with BusinessEnvironment() as env:
        initial = await env.snapshot()
        proposal = await env.service.chat(
            ChatRequest(message="取消订单 ORD10003", user_id="u_demo"), trace_id="proposal"
        )

        async def commit_failure(db):
            raise RuntimeError("synthetic commit failure")

        monkeypatch.setattr(env.service, "_commit", commit_failure)
        with pytest.raises(RuntimeError):
            await env.service.chat(
                ChatRequest(
                    message="确认",
                    user_id="u_demo",
                    session_id=proposal.session_id,
                    confirm_action_id=proposal.pending_action.action_id,
                ),
                trace_id="commit-failed",
            )
        actual = await env.snapshot()
        assert score_goal(initial, actual, EnvironmentExpectation(), [])["success"]
        assert not score_goal(
            initial,
            actual,
            EnvironmentExpectation(
                orders={"ORD10003": "cancelled"}, allowed_mutations=["ORD10003"]
            ),
            [],
        )["success"]
