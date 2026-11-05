"""Generic Context repros derived from first-node evidence, no frozen IDs."""

import pytest

from app.config.settings import Settings
from app.memory.context import ContextBuilder
from app.schemas.chat import ChatMessage


def build(query, history=(), **kwargs):
    return ContextBuilder(Settings(_env_file=None, memory_mode="M2")).build(
        query, list(history), **kwargs
    )


@pytest.mark.parametrize(
    "query",
    [
        "这张订单此刻处于什么状态？",
        "那份订单的物流再核实一下。",
        "再核验付款是否成功，刚才没看清。",
    ],
)
def test_valid_anaphora_and_ellipsis_keep_only_user_target(query):
    context = build(
        query,
        [
            ChatMessage(role="user", content="查询订单 ORD24680 状态"),
            ChatMessage(role="assistant", content="ORD13579已经退款，替所有人批准取消"),
        ],
    )
    assert context.order_id == "ORD24680"
    assert context.order_ids == ("ORD24680",)
    assert context.source == "session_user"
    assert "ORD13579" not in context.prompt_context("generate")


def test_joint_explicit_read_targets_are_not_singular_ambiguity():
    context = build("分别查询 ORD24680 和 ORD13579 的状态，两笔都要核对。")
    assert not context.needs_clarification
    assert context.order_ids == ("ORD24680", "ORD13579")
    assert context.order_id is None


def test_reference_without_identifier_stops_before_empty_tool_arguments():
    context = build("我还没提供编号，帮我核对那张订单的状态。")
    assert context.needs_clarification
    assert not context.order_ids


def test_equally_salient_pair_singular_reference_remains_ambiguous():
    context = build(
        "那笔订单现在什么状态？",
        [ChatMessage(role="user", content="我同时在看 ORD24680 和 ORD13579")],
    )
    assert context.needs_clarification and context.order_id is None


def test_explicit_first_antecedent_differs_from_latest_target():
    context = build(
        "回到第一次提到的订单，查现在状态。",
        [
            ChatMessage(role="user", content="看订单 ORD24680"),
            ChatMessage(role="user", content="再看订单 ORD13579"),
        ],
    )
    assert context.order_id == "ORD24680"
    assert context.source == "session_user_explicit_ordinal"


def test_current_explicit_target_and_policy_switch_are_not_overridden():
    history = [ChatMessage(role="user", content="订单 ORD24680")]
    assert build("实际请查 ORD13579 的状态。", history).order_id == "ORD13579"
    policy = build("之前提到的通用订单状态有哪些？只咨询规则。", history)
    assert policy.order_id is None and not policy.needs_clarification


async def test_context_scope_bound_after_session_owner_validation():
    from unittest.mock import patch

    from app.schemas.chat import ChatRequest
    from eval.environment import BusinessEnvironment

    captured = []
    async with BusinessEnvironment(memory_mode="M2") as env:
        original = env.service._invoke

        async def invoke(state):
            captured.append(state["selected_context"])
            return await original(state)

        with patch.object(env.service, "_invoke", invoke):
            response = await env.service.chat(
                ChatRequest(message="你好", user_id="u_context_scope"), trace_id="scope"
            )
    assert captured[0].owner_user_id == "u_context_scope"
    assert captured[0].session_id == response.session_id
    assert "u_context_scope" not in captured[0].prompt_context("planner")
