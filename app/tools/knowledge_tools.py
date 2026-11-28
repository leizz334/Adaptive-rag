"""Knowledge tools: policy search, coupons, warranty and escalation."""

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.retrieval.hybrid import HybridRetriever
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext


class KnowledgeSearchInput(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="1–200 字的规则问题，写出要判断的政策条件",
        examples=["定制商品适用七天无理由退货吗"],
    )


class CouponInput(BaseModel):
    user_id: str | None = Field(
        default=None,
        max_length=64,
        description="兼容参数。当前规则与身份无关，可省略",
        examples=[None],
    )


class WarrantyInput(BaseModel):
    sku: str = Field(
        min_length=2,
        max_length=32,
        description="2–32 字的商品 SKU，用于标明查询对象",
        examples=["SKU-HEADSET"],
    )


class SearchKnowledgeTool(Tool):
    name = "search_knowledge"
    description = (
        "检索 FAQ、退换货、配送、保修等通用规则。返回最多 4 个 chunks[{chunk_id,title,content}]，"
        "每段 content 最多 400 字符。根据相关文段回答规则，个别订单、退款单、物流和库存使用对应业务工具。"
        "券码与叠用规则用 get_coupon；空结果或缺少相关条款时说明没有查到依据。"
    )
    risk = ToolRisk.READ
    input_model = KnowledgeSearchInput

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    async def execute(self, parsed: KnowledgeSearchInput, context: ToolContext) -> ToolResult:
        chunks = await self._retriever.retrieve(parsed.query, top_k=4)
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "chunks": [
                    {"chunk_id": c.chunk_id, "title": c.title, "content": c.content[:400]}
                    for c in chunks
                ]
            },
        )


class GetCouponTool(Tool):
    name = "get_coupon"
    description = (
        "返回通用优惠券规则 coupons[{code,desc}]，用于券码、满减、包邮和叠用条件。"
        "规则来自工具内置数据，user_id 不影响结果。账户领券状态、个人资格和核销结果无法核实。"
        "查询订单总额用 get_order。"
    )
    risk = ToolRisk.READ
    input_model = CouponInput

    async def execute(self, parsed: CouponInput, context: ToolContext) -> ToolResult:
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "coupons": [
                    {"code": "NEW10", "desc": "新客满 99 减 10，不与品类券叠用"},
                    {"code": "SHIP0", "desc": "满 59 包邮，偏远地区除外"},
                ]
            },
        )


class GetWarrantyTool(Tool):
    name = "get_warranty"
    description = (
        "给定 SKU 时返回内置的通用保修摘要 {sku,warranty_months,note}。SKU 原样返回，"
        "结果没有验证 SKU 是否存在，也没有核对商品特有保修或某笔订单的保修资格。"
        "通用保修政策细节用 search_knowledge，核对目录商品用 get_product_detail。"
    )
    risk = ToolRisk.READ
    input_model = WarrantyInput

    async def execute(self, parsed: WarrantyInput, context: ToolContext) -> ToolResult:
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "sku": parsed.sku,
                "warranty_months": 12,
                "note": "人为损坏不在保，电子凭证见订单详情",
            },
        )


class EscalateInput(BaseModel):
    reason: str = Field(
        min_length=1,
        max_length=200,
        description="转人工原因摘要，如「用户要求值班经理介入」；不要填 order_id 代替原因",
    )


class EscalateToHumanTool(Tool):
    name = "escalate_to_human"
    description = (
        "生成转人工请求回执，适用于用户要求转人工或业务查询无法处理的情况。"
        "reason 为 1–200 字的转接原因，如「用户要求值班经理审核退款」。"
        "返回会话派生 ticket_id、queue:human 和 reason。回执不证明已持久化工单、进入队列或接通人工。"
    )
    risk = ToolRisk.EXTERNAL
    input_model = EscalateInput

    async def execute(self, parsed: EscalateInput, context: ToolContext) -> ToolResult:
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "ticket_id": f"t_{context.session_id[:10]}",
                "queue": "human",
                "reason": parsed.reason,
            },
        )
