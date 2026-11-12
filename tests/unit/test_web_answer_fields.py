"""Synthetic Web0 regressions: requested item facts survive coverage recovery."""

import json

import pytest

from app.agents.answer_evidence import safe_answer
from app.agents.goals import coverage, read_tools
from app.agents.nodes.generate import generate_node
from app.core.enums import RetrievalStrategy
from app.core.exceptions import LLMProviderError
from app.providers.base import LLMResponse
from app.schemas.agent import ToolResult

QUERY = "列出订单ORD8080的商品名称、数量和是否定制，以及已有退款记录"


def tools():
    return [
        ToolResult(
            name="get_order_items",
            success=True,
            output={
                "order_id": "ORD8080",
                "items": [
                    {"sku": "SKU-TOWEL", "name": "浴巾", "quantity": 2, "customized": True},
                    {"sku": "SKU-SOAP", "name": "香皂", "quantity": 3, "customized": False},
                ],
            },
        ),
        ToolResult(name="get_refund_status", success=True, output={"refunds": []}),
    ]


class Model:
    def __init__(self, answer=None):
        self.answer = answer

    async def generate(self, *args, **kwargs):
        if self.answer is None:
            raise LLMProviderError("synthetic outage")
        return LLMResponse(content=json.dumps({"answer": self.answer}, ensure_ascii=False))


def test_name_only_request_is_an_order_items_goal():
    assert read_tools("订单ORD8080商品名称是什么") == ["get_order_items"]


@pytest.mark.parametrize(
    "answer",
    [
        "没有查到该订单的退款单。",
        "没查到退款申请记录。",
        "该订单没有退款记录。",
    ],
)
def test_empty_refund_natural_absence_is_conveyed(answer):
    assert coverage("查看退款记录", tools(), answer)[0]["conveyed"] is True


@pytest.mark.parametrize(
    "answer", ["退款已完成，无需等待。", "未发货，退款已到账。", "没有发货但退款记录已完成。"]
)
def test_unrelated_negative_does_not_cover_empty_refunds(answer):
    assert coverage("查看退款记录", tools(), answer)[0]["conveyed"] is False


def test_coverage_rejects_omitted_requested_names_and_customized():
    rows = coverage(QUERY, tools(), "SKU-TOWEL 2件；SKU-SOAP 3件。暂无退款记录。")
    assert any(row["conveyed"] is False for row in rows)


def test_safe_recovery_preserves_item_names_and_boolean_flags():
    answer = safe_answer(tools())
    assert "浴巾" in answer and "香皂" in answer
    assert "定制：是" in answer and "定制：否" in answer
    assert "2件" in answer and "3件" in answer


async def test_complete_name_based_answer_is_not_replaced_for_missing_skus():
    answer = "浴巾2件，定制：是；香皂3件，定制：否。没有查到该订单的退款单。"
    result = await generate_node(
        dict(user_query=QUERY, strategy=RetrievalStrategy.AGENT, tool_results=tools()),
        Model(answer),
    )
    assert result["final_answer"] == answer


@pytest.mark.parametrize("answer", [None, "SKU-TOWEL 2件；SKU-SOAP 3件。暂无退款记录。"])
async def test_generation_failure_or_omission_recovers_all_requested_item_fields(answer):
    result = await generate_node(
        dict(user_query=QUERY, strategy=RetrievalStrategy.AGENT, tool_results=tools()),
        Model(answer),
    )
    text = result["final_answer"]
    assert "浴巾" in text and "香皂" in text
    assert "定制：是" in text and "定制：否" in text


@pytest.mark.parametrize(
    "answer",
    [
        "浴巾3件，定制：是，香皂2件，定制：否。暂无退款记录。",
        "浴巾2件，不属于定制，香皂3件，定制：否。暂无退款记录。",
        "浴巾2件，定制：否，香皂3件，定制：是。暂无退款记录。",
        "浴巾2件，定制：是，香皂2件，定制：否。暂无退款记录。",
    ],
)
def test_other_items_fields_cannot_cover_wrong_quantity_or_customization(answer):
    assert any(row["conveyed"] is False for row in coverage(QUERY, tools(), answer))


@pytest.mark.parametrize("status", ["failed", "truncated"])
def test_fallback_does_not_render_names_from_unusable_results(status):
    result = tools()[0]
    result.success = status != "failed"
    result.truncated = status == "truncated"
    assert "浴巾" not in safe_answer([result])


def test_fallback_does_not_invent_missing_customization():
    result = tools()[0]
    for item in result.output["items"]:
        item.pop("customized")
    answer = safe_answer([result])
    assert "浴巾" in answer
    assert "定制：" not in answer
