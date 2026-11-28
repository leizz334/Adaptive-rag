"""Logistics tools: shipment tracking."""

from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class TrackInput(BaseModel):
    order_id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="订单号，3–32 位字母、数字、_ 或 -。仅提供运单号时先询问订单号",
        examples=["ORD10001"],
    )


class TrackShipmentTool(RepositoryBackedTool, Tool):
    name = "track_shipment"
    description = (
        "查询运单号和订单中的物流里程碑。返回 order_id、tracking_no、city、events[{status,at,tracking_no?}]。"
        "city 是收件城市。warehouse 根据付款时间生成，in_transit 根据发货时间生成，delivered 根据签收时间生成。"
        "结果没有快递扫描地点、实时所在城市或预计送达时间。空 events 或空运单号表示对应数据未记录。"
        "查询支付、订单金额或状态用 get_order，查询通用配送规则用 search_knowledge。"
    )
    risk = ToolRisk.READ
    input_model = TrackInput

    async def execute(self, parsed: TrackInput, context: ToolContext) -> ToolResult:
        order = await self.repository.get_visible_order(parsed.order_id, context.user_id)
        events: list[dict[str, Any]] = []
        if order.paid_at:
            events.append({"status": "warehouse", "at": order.paid_at.isoformat()})
        if order.shipped_at:
            events.append(
                {
                    "status": "in_transit",
                    "tracking_no": order.tracking_no,
                    "at": order.shipped_at.isoformat(),
                }
            )
        if order.delivered_at:
            events.append({"status": "delivered", "at": order.delivered_at.isoformat()})
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "order_id": order.order_id,
                "tracking_no": order.tracking_no,
                "city": order.receiver_city,
                "events": events,
            },
        )
