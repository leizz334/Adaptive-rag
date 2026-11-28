---
name: order-tracking
description: 查已有订单的当前状态、订单金额、付款时间、运单及运输轨迹。只有一个目标时选择能提供该目标证据的读取工具；适用于查询现有记录。
metadata:
  adaptive-intents: "logistics,order_inquiry"
  adaptive-goals: "order_status,order_payment,order_amount,shipment,tracking_number"
  adaptive-tools: "get_order,track_shipment"
  adaptive-legacy-name: "order_tracking"
  adaptive-legacy-description: "订单与物流跟踪"
  adaptive-legacy-triggers: "物流|快递|到哪了"
  adaptive-legacy-intents: "logistics,order_inquiry"
---

# 订单及物流查询

核实当前请求指向哪个订单。订单号无法唯一绑定时按既有上下文机制请求澄清。专门的退款、退货和取消请求走对应业务能力。

## Steps

- 查询订单
- 查询物流轨迹
- 解释当前状态与时效

按实际目标调用。订单状态和付款信息用 `get_order`。物流事件及运单号用 `track_shipment`，仅在请求包含两个不同目标时考虑两个工具。根据工具输出解释当前状态。没有扫描城市或预计时效的有效记录时，说明这些信息无法核实。
