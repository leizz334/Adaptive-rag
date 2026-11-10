"""Independent safety counterexamples for the P4 HTTP contract corrections."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.answer_evidence import safe_answer
from app.agents.goals import coverage
from app.core.enums import OrderStatus
from app.core.exceptions import InvalidRequestError
from app.repositories.order_repository import OrderRepository
from app.schemas.agent import ToolResult


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDING,
        OrderStatus.REFUNDED,
    ],
)
async def test_confirming_an_ineligible_cancel_cannot_mutate_or_write_audit(status):
    session = AsyncMock()
    repository = OrderRepository(session)
    repository.get_order = AsyncMock(
        return_value=SimpleNamespace(order_id="ORD72819", status=status)
    )
    repository.update_status = AsyncMock()
    repository.write_audit = AsyncMock()

    with pytest.raises(InvalidRequestError, match="only unpaid or paid-unshipped"):
        await repository.cancel_order("ORD72819", trace_id="independent-review")

    repository.update_status.assert_not_awaited()
    repository.write_audit.assert_not_awaited()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("source_success", [False, True])
def test_policy_recovery_cannot_establish_current_order_facts(source_success):
    results = [
        ToolResult(
            name="get_order",
            success=False,
            output={"order_id": "ORD72819", "status": "shipped", "total_cents": 812345},
            error="synthetic lookup failure",
        ),
        ToolResult(
            name="search_knowledge",
            success=source_success,
            output={
                "chunks": [{"content": "政策：退货不证明订单已发货或任何金额。"}],
                "order_id": "ORD72819",
                "status": "shipped",
                "total_cents": 812345,
                "fallback_from": "get_order",
            },
        ),
    ]

    answer = safe_answer(results)
    goals = coverage("查询 ORD72819 当前订单状态和总金额", results, answer)
    assert goals and all(not goal["observed"] for goal in goals)
    assert "8123.45" not in answer and "已发货" not in answer
    assert "无法可靠确认" in answer
