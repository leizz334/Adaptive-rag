"""Pure, allowlisted business facts for answer failure recovery; no tool execution."""

from __future__ import annotations

import re
from decimal import Decimal

from app.schemas.agent import ToolResult

ORDER_STATUS = {
    "created": "待支付",
    "paid": "已支付",
    "shipped": "已发货",
    "delivered": "已签收",
    "cancelled": "已取消",
    "refunding": "退款中",
    "refunded": "已退款",
}
SHIPMENT_STATUS = {"warehouse": "仓库处理中", "in_transit": "运输中", "delivered": "已签收"}


def _identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{2,64}", value) else None


def _money(value):
    return f"{Decimal(value)/100:.2f}元（人民币）" if type(value) is int and value >= 0 else None


def verified_facts(results: list[ToolResult]) -> list[str]:
    """Only known fields in successful nontruncated outputs become factual sentences."""
    facts = []
    for index, result in enumerate(results):
        if not result.success or result.truncated:
            continue
        data = result.output
        oid = _identifier(data.get("order_id"))
        sku = _identifier(data.get("sku"))
        stale_status = (
            result.name == "get_order"
            and oid
            and any(
                later.name in {"cancel_order", "create_refund_request"}
                and later.success
                and later.output.get("order_id") == oid
                for later in results[index + 1 :]
            )
        )
        if result.name == "get_order" and oid:
            status = ORDER_STATUS.get(str(data.get("status")))
            if status and not stale_status:
                facts.append(f"订单 {oid} 当前订单状态：{status}。")
            amount = _money(data.get("total_cents"))
            if amount:
                facts.append(f"订单 {oid} 总金额：{amount}。")
        elif result.name == "track_shipment" and oid:
            tracking = _identifier(data.get("tracking_no"))
            if tracking:
                facts.append(f"订单 {oid} 的物流单号：{tracking}。")
            events = data.get("events")
            if isinstance(events, list):
                if not events:
                    facts.append(f"订单 {oid} 暂无物流轨迹，不能确认签收。")
                elif isinstance(events[-1], dict):
                    status = SHIPMENT_STATUS.get(str(events[-1].get("status")))
                    if status:
                        facts.append(f"订单 {oid} 的物流状态：{status}。")
        elif result.name == "get_order_items" and isinstance(data.get("items"), list):
            for item in data["items"]:
                if not isinstance(item, dict):
                    continue
                item_sku = _identifier(item.get("sku"))
                qty = item.get("quantity")
                if item_sku and type(qty) is int and qty >= 0:
                    facts.append(f"订单商品 {item_sku} 数量：{qty}件。")
        elif result.name in {"get_product_detail", "check_inventory"} and sku:
            inventory = data.get("inventory")
            if type(inventory) is int and inventory >= 0:
                facts.append(f"商品 {sku} 库存：{inventory}件。")
            if result.name == "get_product_detail":
                for key, field_label in (("name", "名称"), ("description", "资料")):
                    value = data.get(key)
                    if isinstance(value, str) and value.strip() and len(value) <= 300:
                        facts.append(f"商品 {sku} {field_label}（工具原文）：{value.strip()!r}。")
                price = _money(data.get("price_cents"))
                if price:
                    facts.append(f"商品 {sku} 价格：{price}。")
        elif result.name == "get_warranty" and sku:
            months = data.get("warranty_months")
            if type(months) is int and 0 <= months <= 1200:
                facts.append(f"商品 {sku} 保修期：{months}个月。")
                # Only the current, explicit tool contract's known exclusion.
                if data.get("note") == "人为损坏不在保，电子凭证见订单详情":
                    facts.append(f"商品 {sku} 人为损坏不在保，电子凭证见订单详情。")
        elif result.name == "get_refund_status" and isinstance(data.get("refunds"), list):
            if not data["refunds"]:
                facts.append("本次查询暂未发现退款申请记录，不能据此声称退款完成。")
            for row in data["refunds"]:
                if not isinstance(row, dict):
                    continue
                rid = _identifier(row.get("refund_id"))
                label = {
                    "requested": "已申请",
                    "processing": "处理中",
                    "completed": "已完成",
                    "rejected": "被拒绝",
                }.get(str(row.get("status")))
                if rid and label:
                    facts.append(f"退款单 {rid} 状态：{label}。")
                    amount = _money(row.get("amount_cents"))
                    if amount:
                        facts.append(f"退款单 {rid} 金额：{amount}。")
        elif result.name == "cancel_order" and oid and data.get("status") == "cancelled":
            facts.append(f"订单 {oid} 已取消。")
        elif (
            result.name in {"create_refund_request", "create_return_request"}
            and oid
            and data.get("status") == "requested"
        ):
            noun = "退款" if result.name == "create_refund_request" else "退货"
            facts.append(f"订单 {oid} 的{noun}申请已提交，尚不代表款项到账。")
    return list(dict.fromkeys(facts))


def safe_answer(results: list[ToolResult]) -> str:
    facts = verified_facts(results)
    limitation = "其余所需结论暂时无法可靠确认，请补充信息或转人工；上述事实不代表其他操作已完成。"
    return (
        ("以下是本次工具结果可确认的信息：\n" + "\n".join(facts) + "\n" + limitation)
        if facts
        else "当前无法可靠确认所需结论。现有证据不足以完成答复，请补充信息或转人工。"
    )
