"""Order tools: order and item lookup."""

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class OrderIdInput(BaseModel):
    order_id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="用户的订单号，3–32 位字母、数字、_ 或 -。运单号、退款单号与手机号不可代入",
        examples=["ORD10001"],
    )


class GetOrderTool(RepositoryBackedTool, Tool):
    name = "get_order"
    description = (
        "查询当前用户的订单状态、订单总额、付款与发货记录。"
        "返回 order_id、status、total_cents（分）、created_at、paid_at、shipped_at、delivered_at、"
        "tracking_no、receiver_city、items 和 user_id。时间为空表示该时间未记录。"
        "total_cents 是订单总额，缺少支付方式、支付流水和优惠明细。"
        "仅查商品明细用 get_order_items，物流轨迹用 track_shipment，退款单状态与金额用 get_refund_status。"
    )
    risk = ToolRisk.READ
    input_model = OrderIdInput

    async def execute(self, parsed: OrderIdInput, context: ToolContext) -> ToolResult:
        order = await self.repository.get_visible_order(parsed.order_id, context.user_id)
        return ToolResult(name=self.name, success=True, output=order.model_dump(mode="json"))


class GetOrderItemsTool(RepositoryBackedTool, Tool):
    name = "get_order_items"
    description = (
        "仅查订单中的行项目，适用于买了什么、数量、购买单价或是否定制。"
        "返回 items[{sku,name,quantity,unit_price_cents,customized}]，单价单位为分。"
        "定制标记可配合政策判断退货资格。查询订单状态或订单总额用 get_order，其结果也包含 items。"
    )
    risk = ToolRisk.READ
    input_model = OrderIdInput

    async def execute(self, parsed: OrderIdInput, context: ToolContext) -> ToolResult:
        order = await self.repository.get_visible_order(parsed.order_id, context.user_id)
        return ToolResult(
            name=self.name,
            success=True,
            output={"items": [item.model_dump() for item in order.items]},
        )
