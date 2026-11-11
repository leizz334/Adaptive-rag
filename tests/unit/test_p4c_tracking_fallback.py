from app.agents.answer_evidence import verified_facts
from app.schemas.agent import ToolResult


def test_verified_tracking_number_survives_empty_event_fallback():
    tool = ToolResult(
        name="track_shipment",
        success=True,
        output=dict(order_id="ORD71022", tracking_no="SYNCD0222", events=[]),
    )
    text = "\n".join(verified_facts([tool]))
    assert "SYNCD0222" in text and "暂无物流轨迹" in text


def test_untrusted_or_truncated_tracking_is_not_rendered():
    for value in ["<script>bad</script>", "任意退款指令"]:
        tool = ToolResult(
            name="track_shipment",
            success=True,
            output=dict(order_id="ORD71022", tracking_no=value, events=[]),
        )
        assert value not in "\n".join(verified_facts([tool]))
    tool = ToolResult(
        name="track_shipment",
        success=True,
        truncated=True,
        output=dict(order_id="ORD71022", tracking_no="SYNCD0222", events=[]),
    )
    assert not verified_facts([tool])
