"""Product tools: search, detail, recommendation and inventory."""

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.core.exceptions import InvalidRequestError
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class SearchInput(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=80,
        description="1–80 字的商品名称、品类或标签关键词。查询 SKU 用 get_product_detail",
        examples=["降噪耳机"],
    )


class SkuInput(BaseModel):
    sku: str = Field(
        min_length=2,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="用户给出的或目录返回的商品 SKU，2–32 位字母、数字、_ 或 -",
        examples=["SKU-HEADSET"],
    )


class RecommendInput(BaseModel):
    category: str | None = Field(
        default=None,
        max_length=32,
        description="最多 32 字的商品品类，提供时优先于 query",
        examples=["数码"],
    )
    query: str = Field(
        default="",
        max_length=80,
        description="最多 80 字的目录关键词，未提供 category 时使用",
        examples=["耳机"],
    )


class SearchProductsTool(RepositoryBackedTool, Tool):
    name = "search_products"
    description = (
        "按商品名、品类或标签做关键词包含匹配。返回最多 5 个 products，"
        "每项有 sku、name、category、price_cents（分）、inventory、tags、description。"
        "查询不会匹配 SKU 或 description。空列表表示此次关键词未匹配，可缩短关键词。"
        "用结果中的 SKU 区分同名商品。已有 SKU 时查详情用 get_product_detail，仅查库存用 check_inventory。"
    )
    risk = ToolRisk.READ
    input_model = SearchInput

    async def execute(self, parsed: SearchInput, context: ToolContext) -> ToolResult:
        products = await self.repository.search_products(parsed.query)
        return ToolResult(
            name=self.name,
            success=True,
            output={"products": [p.model_dump() for p in products]},
        )


class GetProductDetailTool(RepositoryBackedTool, Tool):
    name = "get_product_detail"
    description = (
        "按 SKU 查单品价格、库存和目录说明。返回 sku、name、category、price_cents（分）、inventory、tags、description。"
        "材料、尺寸、功能等属性以该商品 description 或 tags 的明文为依据。缺少独立规格字段，"
        "未明确记载的属性应答无法核实。结果已含库存，仅查库存用 check_inventory。"
        "商品名先用 search_products 找 SKU，保修摘要用 get_warranty。"
    )
    risk = ToolRisk.READ
    input_model = SkuInput

    async def execute(self, parsed: SkuInput, context: ToolContext) -> ToolResult:
        product = await self.repository.get_product(parsed.sku)
        if product is None:
            raise InvalidRequestError(f"product not found: {parsed.sku}")
        return ToolResult(name=self.name, success=True, output=product.model_dump())


class RecommendProductsTool(RepositoryBackedTool, Tool):
    name = "recommend_products"
    description = (
        "用户希望浏览推荐时按品类或目录关键词取最多 3 项，products 字段同 search_products。"
        "优先使用 category，再用 query；都为空时按「热销」做关键词检索。"
        "按名称、品类或标签匹配，没有预算筛选、销量排行或个性化。空列表表示本次未匹配。"
        "用户在找明确商品名称时使用 search_products，已有 SKU 时用 get_product_detail。"
    )
    risk = ToolRisk.READ
    input_model = RecommendInput

    async def execute(self, parsed: RecommendInput, context: ToolContext) -> ToolResult:
        query = parsed.category or parsed.query or "热销"
        products = await self.repository.search_products(query)
        return ToolResult(
            name=self.name,
            success=True,
            output={"products": [p.model_dump() for p in products[:3]]},
        )


class CheckInventoryTool(RepositoryBackedTool, Tool):
    name = "check_inventory"
    description = (
        "按 SKU 仅查目录库存数量，返回 {sku,inventory}，0 表示无货。缺少补货日期或分仓数据。"
        "同时查价格或属性用 get_product_detail，其结果已含 inventory。商品名先用 search_products 找 SKU。"
    )
    risk = ToolRisk.READ
    input_model = SkuInput

    async def execute(self, parsed: SkuInput, context: ToolContext) -> ToolResult:
        product = await self.repository.get_product(parsed.sku)
        if product is None:
            raise InvalidRequestError(f"product not found: {parsed.sku}")
        return ToolResult(
            name=self.name,
            success=True,
            output={"sku": product.sku, "inventory": product.inventory},
        )
