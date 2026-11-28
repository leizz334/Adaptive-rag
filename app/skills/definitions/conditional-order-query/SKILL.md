---
name: conditional-order-query
description: 用户明确要求按支付结果决定是否查同一订单商品明细时，先核实该订单的支付字段，条件成立才读取明细，保留其他独立的只读目标。
metadata:
  adaptive-intents: "order_inquiry"
  adaptive-goals: "order_items,order_payment"
  adaptive-tools: "get_order,get_order_items"
  adaptive-activation: "condition"
---

# 按支付结果查询订单明细

适用于“订单已经付款的话，帮我查该订单的商品明细”这类单订单依赖。要求根据外部审批、物流或其他不可核实事件决定，或要求条件成立后进行写操作时，需要沿既有路径澄清和确认。

先用 `get_order` 获取该订单的真实支付时间与状态。条件成立才调用同一订单的 `get_order_items`。前置结果显示未付款时说明并略过明细。支付证据不完整时将条件保留为未知。前置工具失败时告知相应读取失败，跳过依赖步骤。独立且已经取证的其他目标仍可答复。

即使 `get_order` 返回了附带商品信息，付款条件未验证时仍依照用户要求限制明细的披露。
