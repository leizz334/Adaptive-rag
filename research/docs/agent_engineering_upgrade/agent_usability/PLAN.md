# Agent 可用性完善 Implementation Plan

**Goal:** 新请求可依据可信 usage 审计结算，提供安全的8000/8001模式入口，以零付费回归验证业务流程，明确真实业务NOT_RUN。

**Architecture:** 保留原预算限制指纹、每次HTTP预留和原始attempts。添加只存元数据的预留证据/结算表，在同一SQLite立即事务中完成结算；无可信usage的历史记录保守保留。模式采用不同端口整页切换，凭证与私有会话留在各自origin，不代理Bearer或调用模型探测。

**Tech Stack:** 现有FastAPI、LangGraph、React、HTTPX、SQLite账本、WSL Docker、Chromium。

**Spec:** 本轮用户P1/P2/P3及不授权付费的约束。

## Global Constraints

- 复用当前worktree；保留.env、所有旧卷/账本/Stash/Gold/研究数据，Experience Active=OFF。
- 本轮模型付费授权为零；不得使用现有Key发起请求，禁止自动扩大或重置额度。
- 旧3条记录没有在账本中持久化逐请求usage，不从报告自动回填返额；真实原账本保持不变，在副本上验证兼容升级。
- 原始预留不可覆盖、请求次数不可退回；仅完整成功的供应商响应且usage可信时可结算Token和按配置上界的费用。
- 非2xx/截断/取消/断流/不可信usage保留原预留；不确定状态继续阻止后续消费。
- 真实与Mock结果严格分列；Mock仅复用现有Agent和工具，不能伪造数据库工具返回或绕过Owner/HITL。

## Review Focus

- 并发和重启不会重复返额；损坏、超界、重复矛盾usage不能回收额度。
- 成功响应在消费完成/关闭确认前不能释放；SSE必须有完整终止和可信usage。
- UI切换不转移凭证、查询参数、会话、草稿、私有知识库或未完成写请求。
- 所有跨origin探测仅为无Bearer、credentials=omit的只读metadata；业务API不开放跨origin权限。
- 服务端付费授权独立于服务启动和前端；默认关闭，释放额度不等于授权发起付费请求。

## Shared Interfaces

Budget component owned by budget agent:

- `AttemptLedger.snapshot()`保留`requests,tokens,usd,pending,uncertain,completed`，其中tokens/usd为结算后的有效占用；新增原始`reserved_tokens,reserved_usd,settled`审计指标。
- 原`complete(id)`仍为保守完成；新增`settle(id, *, prompt_tokens, completion_tokens, total_tokens, response_sha256, source)`；具体原子实现由预算子任务定义并记录，不暴露HTTP结算接口。
- `BudgetedTransport(..., dispatch_enabled: bool = True)`，false在预留和网络发送前拒绝；RealDev入口显式传入服务端授权，不能因注入transport而绕过。

Backend metadata owned by root:

`GET /api/v1/runtime-status`返回`{mode: "offline"|"deepseek"|"unknown", available: boolean, reason: string, message: string, verification_only: boolean}`。不含Key、Bearer、账本路径、费用/计数。reason包含ready/payment_not_authorized/budget_not_ready/budget_exhausted/dependencies_unavailable/unsupported_deployment。

仅此GET路径允许固定loopback8000/8001 origin的无凭证CORS；其余业务/认证API不新增CORS。RealDev使用`REAL_AGENT_PAID_AUTHORIZED`（默认false），即使预算有余额也不能发送未经授权的模型HTTP。

Frontend owned by frontend agent:

- 登录前、登录后都有模式入口；只探测固定127.0.0.1:8000/8001上述metadata，超时/不可用/模型不匹配明确显示原因，不自动降级。
- 选择可用模式后清空当前凭证/状态并整页导航到目标origin的`/`，每次重新认证。阻止进行中请求切换或明确停止流程；BFCache返回也重新认证。
- 收紧业务API为当前origin，避免VITE_API_BASE跨环境携带Bearer。

## Tasks

- [ ] P1：预算RED→GREEN、legacy副本迁移/审计不变、并发/进程/重启/重试/JSON/SSE/异常覆盖，单独提交。
- [ ] P2：新增默认关闭的付费锁和只读模式状态，MockTransport真实HTTP业务测试订单/多轮/RAG/异常/HITL，真实场景全部NOT_RUN，单独提交。
- [ ] P3：模式入口、原因、凭证与origin隔离、前端测试/构建和Chromium E2E；8000 Offline回归，单独提交。
- [ ] DELIVERY：原卷/旧账本/Stash/历史文件保护核对，必要API镜像更新只替换8000 API并保留回滚；零付费Mock服务结束后停止，中文报告/普通Push/精确HEAD。

用户已明确授权实现上述功能，按既定安全约束直接执行；无需为常规实现决策重复请求许可。需要新的真实付费授权时停止相关调用并标记NOT_RUN。
