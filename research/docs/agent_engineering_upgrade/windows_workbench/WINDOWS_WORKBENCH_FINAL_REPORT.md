# Windows Docker 工作台修复验收

日期：2026-11-13。W1–W3 已分别提交，W4 实测完成，最终普通 Push 与远端 HEAD 校验结果由本目录交付状态记录。付费 DeepSeek 请求 **0**，Experience Active 始终关闭。

## 工作台回答根因

指定问题“定制商品过了七天，但有质量问题还能退吗？”在原工作台实际返回 HTTP 200、正确售后 Intent、single 路由；Retrieval 无异常但结果为 0，引用为空、Token 用量 0，Generate 返回正常无资料兜底，Faithfulness 在 Offline 下不调用模型。

原因是**当前用户私有知识库没有对应政策，且 Offline 只支持有限规则和原文节选**。仓库公共政策不会越过 Owner 边界自动进入私有库。本轮没有强改模型、伪造回答或放宽检索权限。隔离环境上传合成政策后，同一问题返回真实引用和政策原文；订单多轮、私有 KB 隔离、HITL/幂等三个原业务场景均通过。[W1 实测](evidence/W1-isolated-verification.md)

## 前端和后台保留

已删除前端 Experience Shadow 导航/页面/组件、独占测试、静态实验 JSON、专属样式和相关状态；没有专用后台 API 被前端删除波及。导航保留对话、会话及私有知识库，欢迎页改为正常助手文案，Offline 提示由服务端 capabilities 决定，明确说明资料与能力边界。

后台 `app/experience`、经验提取/Repository/Applicability/Shadow/审核、数据库结构和历史证据未改；保护清单 **6239 个现有文件哈希全部不变**，Stash 和人工审核文件保留。原 Bearer、Owner、HITL、幂等与 Redis fail-closed 机制保持。[保护核对](evidence/W4-preservation-and-secret-scan.json)

## Offline 和 Real Agent Dev

- 默认 `compose.showcase.yml` 继续零付费 Offline，不读取主机 Key 来偷偷切换模型。
- 新增 `compose.agent-dev.yml` 和 `app.demo.real_dev`，明确服务端启用，复用原 FastAPI、LangGraph、Memory、RAG、Tools 和 HITL；前端没有模型/付费开关。
- Key 只读私有文件或服务端环境变量；Compose 只保存 secret 文件引用。缺 Key、缺显式有限预算、异常账本均拒绝启动/消费，不静默回退 Offline。
- 每个模型 HTTP 尝试（含重试、JSON、流式）先原子预留请求/Token/费用，账本独立持久卷保存，重启不清零；不确定/取消/中断保留预留并阻止自动重放。账本不保存问题、回答、Header 或 Key。
- 独立项目默认 loopback 8001，隔离数据卷与网络；健康检查明确验证 PG、Redis、私有向量库和认证，不发送模型请求。启动说明与必需预算变量见 [安全启动文档](../../../../docs/real-agent-dev.md)。本轮只用假 Key 和 MockTransport 验证 Real Dev，没有启动真实付费模式。

## 实际验证结果

| 检查 | 结果 |
| --- | --- |
| 完整后端 pytest（含真实依赖及 HTTP/SSE/认证） | **1023 PASS、0 FAIL、1 历史 SKIP** |
| 历史 214 场景 | **0 新增回归**；202 PASS、12 原有非 PASS 保留 |
| 前端 | **22 测试 PASS、类型检查 PASS、构建 PASS** |
| 真实 Chromium | **7/7 PASS**；HTTP/SSE、多轮、引用/私有 KB、HITL、幂等、身份切换/刷新、手机导航 |
| Real Dev / 预算 / Offline 兼容组合 | **72 PASS**，含健康检查缺陷 RED→GREEN |
| Ruff check / Mypy / pip check | **PASS**；Mypy 162 个源文件 |
| 全目录 Ruff format | 一份上一轮未跟踪环境脚本未格式化；按保护约束未改。明确排除该单一旧文件后的项目格式检查 PASS |
| Docker 镜像 | 当前应用 150 个 Python 文件与隔离运行镜像逐字节一致 |

[后端详细结果](evidence/w4_backend_20261113_01/CHECKS.md) · [浏览器最终结果](evidence/W4-browser-final.json) · [预算验证](evidence/W3-budget-verification.json) · [配置与集成](evidence/W3-final-targeted.json)

首次浏览器 6/7 的失败保留：A 用户已有 W1 同内容政策，正确引用旧文档而非新重复文档。将测试改为 B 用户空知识库后，单场景及完整 7 场景通过；没有改检索/生成，也没有清空旧政策或重置已取消订单。[首次记录](evidence/W4-browser-first-run.json)

## 运行状态与剩余限制

- 原 `8000` 用户项目的容器 ID、启动时间、镜像、端口及挂载均未变化。依照“不删除现有容器”约束，**原项目没有自动重建，因此仍运行旧镜像**。
- 修复版已在本轮独立 Offline 工作台 `http://127.0.0.1:18083` 完成浏览器验收，保留供复核；本地开发凭证在本目录忽略的 `.private/adaptive-rag-w1-20261113/browser-config.json`，不要发布其内容。切换原 8000 的 API 镜像需另行确认更新容器，数据库卷应继续保留。
- 三个独立后端验证服务已按归属检查停止，测试卷全部保留；未删除任何现有容器、镜像、数据卷或实验数据。
- 真实 DeepSeek 连通性、模型自然语言质量、供应商结算费用及必须依赖代理的网络路径 **NOT_RUN/NOT_TESTED**。费用上界按操作者明确配置的单价估计，不冒充账单。
- 独立审查的一项健康检查重要问题已修复。保留一个小限制：`validate` 的自定义 HTTPS 路径检查比运行时宽；默认官方根路径及 `/v1` 不受影响，其他路径运行时安全拒绝。[审查记录](evidence/final-review.json)
- 原 Git loose-object 目录仍有文件系统错误 1392，没有执行磁盘修复。已保留原对象与 Stash，用校验通过的健康对象库执行提交/普通推送，并将新 pack 无覆盖同步回原仓库可读目录；这不等于原磁盘损坏已消除。

本轮到此为止，不自动部署付费模式、不启动新研究阶段。最终交付提交与远端核验见 `delivery.json`、Git 历史及最终回复。
