# 三类演示：操作、预期与实测

全部使用本run合成数据、真实前后端及PG/Redis/Qdrant，受控OfflineLLMProvider；不是新的DeepSeek质量评估。启动命令见STARTUP.md。登录输入私有配置tokens.a（web_demo_a），切换tokens.b演示另一个主体。Bearer只留内存。

| 场景 | 操作 | 预期 | 本阶段证据 |
|---|---|---|---|
| 多轮订单/Memory/Trace | 查询ORD95101状态金额，追问“这单的商品明细和是否定制”，展开Execution；新建/切回会话，切HTTP模式 | 状态paid、68元、2件非定制帆布包；同session历史数增加、真实get_order/get_order_items、节点顺序/计划/结果可查；新session不混用 | r2_browser_VERIFIED.json / case01 |
| 私有RAG/隔离 | 上传每次唯一标题/ID的txt/md合成规则；检索、聊天引用；切B尝试A文档/Trace；回A完整替换更新后再检索/删除 | 本次真实document_id被引用、可见原文片段；B列表/检索无A资料、删除/Trace404、伪造A user_id403；更新命中新正文、删除不再命中 | r2_browser_VERIFIED.json / case02 |
| Planner/HITL/幂等 | “请取消订单ORD95102”；查看计划和pending，确认，再点击同Action幂等重放；另用ORD95104撤销pending | 确认前无写入，确认后cancelled；同Action无额外写入；跨用户撤销404、已完成撤销409；被撤销提案再确认拒绝且订单仍paid | case03/04 + r2_business.json |
| Experience历史 | 打开Experience Shadow | 原则来源/失败类型/条件/历史审核及版本状态可读；E0/E1/E2对照；NOT_ESTABLISHED/人工0/Active关闭 | case05 |
| 异常与小屏 | 实际浏览器断网发送、恢复后受控网络延迟下停止接收；390px Experience布局 | 安全错误提示，未自动重试；说明服务端可能提交；无水平溢出 | case05/06 |

本轮6个真实浏览器场景全部通过。case03数据库审计取消写入1条，case04撤销后订单仍paid。截图是视觉附件，不替代这些浏览器与SQL证据。

复现命令（API已serve）：

```bash
.venv/bin/python -m scripts.showcase browser --run-id my_interview_01 --cancel-order ORD95102
```

先通过status检查真实依赖、认证及offline模型，再执行单worker、重试0的Playwright。无route mock，不公开含凭据的Trace/HAR；每轮原始报告与日志写入本run独立私有文件，安全汇总可公开。需要预先`cd frontend && npx playwright install chromium --only-shell`。Browser命令不是无副作用健康探测，会执行本run的合成取消订单。

同一合成订单已经取消后不得重置重演首次成功；用尚未取消的ORD95103/95105/95106/95107，或选择全新run。init会拒绝已有run，start/serve保留已有状态。历史R2验证不应自动重放付费实验。
