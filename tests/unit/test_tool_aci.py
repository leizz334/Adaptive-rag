import pytest

from app.core.exceptions import InvalidRequestError
from app.tools.aftersale_tools import CancelOrderTool, GetRefundStatusTool
from app.tools.logistics_tools import TrackShipmentTool
from app.tools.product_tools import CheckInventoryTool, RecommendProductsTool


def test_catalog_surfaces_required_and_optional_schema_parameters() -> None:
    shipment = TrackShipmentTool()
    shipment_catalog = shipment.model_catalog_description()
    assert 'order_id（string，必填，例 "ORD10001"' in shipment_catalog

    recommendation = RecommendProductsTool()
    recommendation_catalog = recommendation.model_catalog_description()
    assert 'category（string | null，可选，例 "数码"' in recommendation_catalog
    assert 'query（string，可选，例 "耳机"' in recommendation_catalog
    assert recommendation.parse({}).model_dump() == {"category": None, "query": ""}


def test_refund_lookup_examples_match_the_runtime_parameter() -> None:
    tool = GetRefundStatusTool()
    properties = tool.openai_schema()["function"]["parameters"]["properties"]
    assert set(properties) == {"order_id"}
    order_id = properties["order_id"]["examples"][0]
    assert tool.parse({"order_id": order_id}).model_dump() == {"order_id": order_id}


def test_read_validation_error_guides_correction_without_echoing_rejected_value() -> None:
    rejected = "private@example.com"
    with pytest.raises(InvalidRequestError) as raised:
        CheckInventoryTool().parse({"sku": rejected})

    assert raised.value.http_status == 400
    message = str(raised.value)
    assert "check_inventory" in message
    assert "sku" in message
    assert "SKU-HEADSET" in message
    assert rejected not in message
    assert "errors.pydantic.dev" not in message


def test_catalog_preserves_write_tool_description() -> None:
    tool = CancelOrderTool()
    assert tool.model_catalog_description() == tool.description
