"""Small read-capability/evidence contract, independent of test data or Gold.

The LLM remains the planner for open tasks. These bounded capabilities express
current tool contracts and conservatively scoped exclusions, not all Chinese.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.schemas.agent import ToolResult

SKU_RE = re.compile(r"(?<![A-Za-z0-9_-])SKU[-_][A-Za-z0-9_-]+", re.I)


@dataclass(frozen=True)
class ReadGoal:
    kind: str
    tool: str
    field: str


def positive_clauses(query: str) -> list[str]:
    raw = query.partition("（会话指代：")[0]
    clauses = re.split(
        r"[，,。；;！!？?\n]|以及|并且|同时|但是|不过|(?:而)?只(?:想|要|需)|仅(?:需|要)", raw
    )
    return [
        c
        for c in clauses
        if c and not re.search(r"不用|不必|无需|不要|不需要|别(?:查|看|列|展)|不想(?:查|看|要)", c)
    ]


def read_goals(query: str) -> tuple[ReadGoal, ...]:
    clauses = positive_clauses(query)
    text = "，".join(clauses)
    header = re.sub(r"(?:物流|快递|运输|配送)(?:的)?状态", "", text)
    found = []
    if any(
        c in header
        for c in (
            "状态",
            "订单阶段",
            "处理阶段",
            "有没有发货",
            "是否发货",
            "是否已发货",
            "有没有支付",
            "支付成功",
        )
    ):
        found.append(ReadGoal("订单状态", "get_order", "status"))
    if any(
        c in header
        for c in ("金额", "实付", "总额", "总价", "合计", "付款", "支付", "一共花", "付了多少")
    ):
        found.append(ReadGoal("订单金额", "get_order", "total_cents"))
    shipment = re.sub(r"(?:走|到|处于).{0,4}(?:订单|处理)阶段", "", text)
    if any(
        c in shipment
        for c in ("物流", "快递", "轨迹", "运单", "运输", "配送", "包裹", "节点", "到哪")
    ):
        found.append(ReadGoal("物流状态", "track_shipment", "events"))
    if any(
        c in text
        for c in (
            "商品明细",
            "订单明细",
            "买了什么",
            "哪些商品",
            "买的东西",
            "各买",
            "几件",
            "几样",
            "几份",
            "数量",
            "定制",
        )
    ):
        found.append(ReadGoal("商品数量", "get_order_items", "items"))
    if (
        any(c in text for c in ("退款单", "退款记录", "退款申请", "退款进度", "退了多少"))
        and "申请退款" not in text
    ):
        found.append(ReadGoal("退款记录", "get_refund_status", "refunds"))
    if SKU_RE.search(query):
        if not re.search(r"ORD\d+|订单", text, re.I):
            found = [
                g
                for g in found
                if g.tool not in {"get_order", "get_order_items", "get_refund_status"}
            ]
        if any(
            c in text
            for c in ("详情", "详细资料", "规格", "参数", "介绍", "价格", "单价", "多少钱")
        ):
            if any(c in text for c in ("详情", "详细资料", "规格", "参数", "介绍")):
                found.append(ReadGoal("商品资料", "get_product_detail", "name"))
            if any(c in text for c in ("价格", "单价", "多少钱")):
                found.append(ReadGoal("商品价格", "get_product_detail", "price_cents"))
        if any(c in text for c in ("库存", "现货", "有货", "剩多少")):
            tool = (
                "get_product_detail"
                if any(g.tool == "get_product_detail" for g in found)
                else "check_inventory"
            )
            found.append(ReadGoal("库存", tool, "inventory"))
        if any(c in text for c in ("保修", "质保")):
            found.append(ReadGoal("保修", "get_warranty", "warranty_months"))
    if found and any(c in text for c in ("规则", "政策", "时效", "条件")):
        found.append(ReadGoal("政策证据", "search_knowledge", "chunks"))
    return tuple(found)


def read_tools(query: str) -> list[str]:
    return list(dict.fromkeys(g.tool for g in read_goals(query)))


def coverage(query: str, results: list[ToolResult], answer: str) -> list[dict]:
    """Conservative factual conveyance hints; not a general semantic Judge."""
    rows = []
    skus = {s.upper() for s in SKU_RE.findall(query)}
    orders = {s.upper() for s in re.findall(r"ORD\d+", query, re.I)}
    for goal in read_goals(query):
        values = [
            r.output[goal.field]
            for r in results
            if r.name == goal.tool
            and r.success
            and not r.truncated
            and goal.field in r.output
            and (
                goal.tool not in {"get_warranty", "get_product_detail", "check_inventory"}
                or not skus
                or r.output.get("sku") in skus
            )
            and (
                goal.tool not in {"get_order", "track_shipment"}
                or not orders
                or r.output.get("order_id") in orders
            )
        ]
        mentioned: bool | None = False
        for value in values:
            if goal.field in {"total_cents", "price_cents"} and type(value) is int:
                mentioned = f"{Decimal(value)/100:.2f}" in answer
            elif goal.field == "status":
                label = {
                    "created": "待支付",
                    "paid": "已支付",
                    "shipped": "已发货",
                    "delivered": "已签收",
                    "cancelled": "已取消",
                    "refunding": "退款中",
                    "refunded": "已退款",
                }.get(str(value), str(value))
                mentioned = label in answer or str(value) in answer
            elif goal.field == "events":
                if value and isinstance(value, list) and isinstance(value[-1], dict):
                    label = {
                        "warehouse": "仓库处理中",
                        "in_transit": "运输中",
                        "delivered": "已签收",
                    }.get(str(value[-1].get("status")), "")
                    mentioned = bool(label) and label in answer
                else:
                    mentioned = "暂无物流轨迹" in answer
            elif goal.field == "warranty_months":
                mentioned = bool(re.search(rf"{re.escape(str(value))}\s*个?月", answer))
            elif goal.field == "inventory":
                mentioned = bool(re.search(rf"{re.escape(str(value))}\s*件", answer))
            elif goal.field == "items":
                mentioned = isinstance(value, list) and all(
                    isinstance(i, dict)
                    and str(i.get("sku", "")) in answer
                    and bool(re.search(rf"{re.escape(str(i.get('quantity')))}\s*件", answer))
                    for i in value
                )
            elif goal.field == "refunds":
                mentioned = "退款" in answer and (bool(value) or "未" in answer or "无" in answer)
            elif goal.field == "chunks":
                mentioned = None
            else:
                mentioned = isinstance(value, str) and value in answer
            if mentioned:
                break
        rows.append(dict(goal=goal.kind, tool=goal.tool, observed=bool(values), conveyed=mentioned))
    return rows
