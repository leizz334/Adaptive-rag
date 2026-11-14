# 真实 Agent 可用性完善报告

日期：2026-11-14。范围仅 P1–P3，复用原工作树；没有新建 Worktree、启动新研究阶段或执行付费请求。

## 结果

| 项目 | 结果与证据 |
|---|---|
| P1 预算结算 | PASS，162 项专项回归包含在后端 891 项通过中 |
| P2 业务流程 | MockTransport + 真实 HTTP/SSE、PostgreSQL、Redis、Qdrant 验证通过；真实模型业务验收 NOT_RUN |
| P3 模式选择 | PASS，54 项前端单元测试、类型检查、构建；实际 Chromium 12/12，无跳过、重试或 flaky |
| 正式 Offline | `http://127.0.0.1:8000` 已更新，四个容器健康，原七项浏览器业务回归通过 |
| 实际消费 | 本轮付费请求 0、付费 Token 0、估算实际费用 $0 |
| 数据保护 | 两份 `.env`、原真实预算账本、原订单/商品、19 个原数据卷、Stash、6239 个受保护历史文件保持不变 |

## P1：可审计结算

原 `attempts`、请求 ID、预留数值和限制指纹不改写。兼容迁移只追加预留证据及结算表；没有可信逐请求 usage 的历史记录继续按原预留计费，不从旧报告补填或返额。

仅完整 2xx 成功响应、模型和协议合法、usage 整数一致且不超原输入/输出边界，并且响应读取及关闭均完成时，才原子追加结算。支持 JSON、SSE 末条内容携带 usage 和独立 usage 事件；SSE 必须完整结束。缺失、异常、截断、取消、失败和不确定请求继续保守处理。`pending/uncertain` 阻止后续自动消费。

`snapshot.tokens/usd` 表示结算后的有效占用；`reserved_tokens/reserved_usd` 保留累计原始预留，`settled` 标识结算数量。请求次数永不返还。持久数据仅含用量、金额、来源及响应哈希，不保存提示词、回答、Key 或 Authorization。费用仍按操作者配置的保守单价估算，不代表供应商账单。

测试覆盖旧账本兼容、并发预留/结算、跨进程及重启、重试逐次计数、重复与冲突结算、事务失败回滚、流式响应中断、并发关闭、畸形协议和错误 usage。保留 RED→GREEN 证据。参见 [P1 证据](evidence/P1-budget.json)。SSE 协议对照 [DeepSeek 官方文档](https://api-docs.deepseek.com/api/create-chat-completion/)。

## P2：逐场景业务验收

以下使用现有 `DeepSeekProvider` 配合明确标识的 HTTPX MockTransport、假 Key 和仅允许回环网络的进程。工具执行、Owner、检索、数据库及 HITL 沿用真实业务实现；回答受控，不能据此宣称真实模型自然语言能力通过。

| 场景 | Mock / 业务链路结果 | 真实 DeepSeek |
|---|---|---|
| 订单 Tool Calling | PASS：ORD95101，工具参数与 SQL 结果对应，paid、6800 分 | NOT_RUN：未授权本轮付费 |
| 多轮 Memory | PASS：同一会话续问商品，M2 上下文关联与商品工具结果对应 | NOT_RUN |
| RAG 引用 | PASS：隔离私有政策真实检索、引用 chunk；另一 Owner 无命中 | NOT_RUN |
| 异常降级与隔离 | PASS：不存在订单、缺少政策、伪造 Owner、跨用户历史均正确处理 | NOT_RUN |
| HITL | PASS：合成订单确认后实际取消；重放未新增审计或重复写入 | NOT_RUN |

实际 HTTP/SSE Trace 和脱敏工具结果见 [P2 验收](evidence/P2-mock-acceptance.json) 及同目录 `P2-*.json`。36 次模拟模型 HTTP 均结算：原预留 137778 Token / $0.0547902，按模拟 usage 净占用 22519 Token / $0.0079527；pending/uncertain 均为 0。这些是测试账本中的模拟数值，实际消费为零。

原真实账本保持逐字节不变：历史 3 次、保守占用 8986 Token / $0.0037866，没有返还或重置。兼容迁移只在副本验证。

新增服务端 `REAL_AGENT_PAID_AUTHORIZED` 默认 `false`，在预留和模型网络发送前拒绝请求，即使有 Key 也不自动消费。Mock 默认同样拒绝，只有本轮假 Key、网络封闭的隔离验证进程显式开启。前端和公开元数据均不能开启付费权限。

## P3：前端模式与安全边界

登录页和工作台提供 Offline / DeepSeek 入口，分别固定到 8000 / 8001。切换是完整页面导航，清除当前凭证、草稿和页面状态，目标要求独立认证；不传递 URL 中的会话参数或私有数据。浏览器返回、刷新及 BFCache 恢复均需重新认证。当前业务请求（包括 SSE 正文）未完成时禁止切换。

切换前重新探测目标状态。未启动、模式不匹配、授权撤销、依赖/预算不可用或超时均明确解释，保留当前登录及草稿，不静默降级。只有公开只读元数据允许两个本地端口的有限 CORS；探测不携带 Bearer/Cookie，拒绝重定向。业务 API 始终限制在当前 origin。Mock 环境明确显示“Mock 验证”。

没有恢复 Experience Shadow 页面。后台 Experience 模块没有改动，正式环境 `EXPERIENCE_MEMORY_MODE=off`，Active 保持 OFF。

实际 Chromium 五项模式测试覆盖凭证和 URL 不转移、返回重新认证、会话/私有文档隔离、不可用解释、请求进行中禁止切换、授权在点击时撤销。另七项原工作台测试覆盖 HTTP/SSE、Memory、工具、RAG CRUD/引用、HITL/幂等、Owner、刷新历史、响应式导航及网络取消。[浏览器结果](evidence/P3-chromium.json)。

## 部署、资源与回滚

只替换正式项目的 API/React 容器，没有重新运行 initialize、Seed 或迁移。升级瞬间全部数据库表指纹一致，PostgreSQL、Redis、Qdrant 容器 ID 和数据卷不变；浏览器随后新增的合成会话/文档/审计保留，取消操作仅使用新增合成订单 `ORD1794658040101`。原八条订单及商品内容再次按哈希核验不变。

| 资源 | 升级前 | 升级后 |
|---|---|---|
| 正式 API 镜像 | `sha256:65a5e165eda8a20789fc32830747dbd946c8ce3d3e50b1782beaa1b98bafb7bf` | `sha256:dea778f7e1250927dc57cf9a7cfde2f338a838283a7c0f1ed530e3017d999e9a` |
| 地址 | 8000 Offline | 8000 Offline，最新模式入口 |
| 原 Real Agent 项目 | 停止 | 仍停止，原账本未写入 |
| 本轮 Mock 8001 + 三个依赖 | 新建隔离验证 | 已停止，数据卷和预算账本保留 |

最终长期运行 **4 个**正式容器。原 19 个数据卷全部保留，另保留本轮 3 个测试卷，总数 **22**。前端当前 index 和所引用构建资源与源码产物哈希一致；增量镜像保留基底的未引用旧哈希资源，不影响当前入口。[最终保护核验](evidence/final-environment.json)。

在固定工作树的 WSL 终端使用已部署容器：

```bash
cd /mnt/d/Code/Adaptive-rag/.worktrees/p3-experience-validation
# 停止正式工作台，保留所有数据
sudo docker compose --env-file /dev/null -p adaptive-rag-showcase \
  -f compose.showcase.yml stop api postgres redis qdrant
# 再次启动现有正式容器
sudo docker compose --env-file /dev/null -p adaptive-rag-showcase \
  -f compose.showcase.yml start postgres redis qdrant api
```

回滚只切换 API 镜像，不清理数据库：

```bash
sudo docker compose --env-file /dev/null -p adaptive-rag-showcase \
  -f compose.showcase.yml \
  -f /home/panda/.adaptive-rag-usability-20261114/rollback.json \
  up -d --no-deps --no-build api
```

回滚标签为 `adaptive-rag-production:rollback-usability-20261114`；升级前数据库备份在同一私有目录 `postgres-before.dump`。正常重建最新版时可使用 `compose.showcase.yml`；复用本轮已构建镜像可叠加本目录 `compose.production.yml`。不要对 Real Dev 使用正式项目名或共享凭证。

## 验证与遗留项

- 后端：891/891 pytest，无失败、无跳过；含 162 项预算/RealDev 专项。网络隔离执行，未调用付费服务。
- 前端：54/54 Vitest、类型检查和生产构建通过；实际 Chromium 12/12。
- Ruff（app、tests、本阶段脚本）、相关格式检查、Mypy（152 个应用文件）通过。
- 独立只读审查无剩余 Important/Critical 问题；敏感值扫描未发现 Key 或完整 Bearer，6239 个受保护历史文件和 Stash 未变。
- 本轮未执行真实 DeepSeek 业务验收；需另行明确请求数、Token 和费用上限，先核对官方价格与现有账本，才可开启服务端付费授权。不能直接把 Mock 的通过结果当作真实模型通过。
- 8001 验证服务现已停止，因此前端 DeepSeek 入口会明确显示不可用。真实环境的独立安全配置和启动步骤见 [Real Agent Dev 文档](../../../../docs/real-agent-dev.md)。模式选择仅导航，不会启动容器。
- 预算是按配置价格计算的应用侧上限，不读取供应商账户账单。本轮没有修改价格或真实 Key。
- 原 Git 对象库的历史文件系统问题未做破坏性修复；提交使用已校验的恢复对象库，并将验证 pack 追加导出。提交/普通 Push 和远端 HEAD 核验结果记录在 `progress.txt`。

所有私有配置、原始浏览器日志及预算文件留在本地，不提交或 Push。阶段完成后停止工作。
