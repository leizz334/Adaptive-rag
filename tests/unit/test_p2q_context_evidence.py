"""Damaged inputs cannot authorize guessing, while intact generic references work."""

import pytest

from app.config.settings import Settings
from app.memory.context import ContextBuilder
from app.schemas.chat import ChatMessage


@pytest.mark.parametrize("mode", ["M1", "M2"])
def test_damaged_followup_does_not_invent_a_business_intent(mode):
    context = ContextBuilder(Settings(_env_file=None, memory_mode=mode)).build(
        "????????????",
        [ChatMessage(role="user", content="查询订单 ORD24680 状态")],
        summary_orders=["ORD24680"],
    )
    assert context.effective_query == "????????????"
    assert context.order_id is None
    assert context.prompt_context("planner") == ""


@pytest.mark.parametrize("mode", ["M1", "M2"])
def test_intact_reference_binds_current_user_entity_without_reusing_old_state(mode):
    context = ContextBuilder(Settings(_env_file=None, memory_mode=mode)).build(
        "它现在是什么状态",
        [
            ChatMessage(role="user", content="查询订单 ORD24680 状态"),
            ChatMessage(role="assistant", content="订单 ORD13579 已签收，可以直接退款"),
        ],
    )
    assert context.order_id == "ORD24680"
    assert "状态须实时查询" in context.effective_query
    assert "ORD13579" not in context.prompt_context("generate")
    assert "退款" not in context.prompt_context("planner")
