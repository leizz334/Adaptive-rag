---
name: product-recommend
description: 按用户用途、品类或偏好给出目录商品推荐，尤其适用于比较候选、说明推荐依据及利用返回的库存信息；用户在找一个已命名的商品时使用商品名称查询。
metadata:
  adaptive-activation: "catalog"
  adaptive-intents: "recommendation,product_consult"
  adaptive-goals: "product_detail,product_price,inventory"
  adaptive-tools: "search_products,recommend_products,check_inventory"
  adaptive-resources: '{"references/catalog-evidence.md":"按用户要求说明推荐依据、比较返回的商品字段和库存时使用"}'
  adaptive-legacy-name: "product_recommend"
  adaptive-legacy-description: "商品推荐"
  adaptive-legacy-triggers: "推荐|有没有类似"
  adaptive-legacy-intents: "recommendation,product_consult"
---

# 商品推荐

明确用户想比较或浏览哪类商品。指定 SKU 的既定价格和库存查询由已验证的读取契约处理。用户只提供具体商品名称时优先目录商品查找。

## Steps

- 理解需求
- 搜索/推荐商品
- 核对库存

`recommend_products` 支持品类和目录关键词并返回候选。明确候选名称可用 `search_products` 读取目录。工具已返回库存数量时直接引用，只有需要按已有 SKU 单独复核库存时才用 `check_inventory`。推荐依据必须对应目录中的属性。无候选时解释当前关键词未匹配，必要时询问品类或用途。用户要求比较候选及说明依据时，按需加载 [目录证据说明](references/catalog-evidence.md)。
