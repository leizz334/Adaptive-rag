# 数据库、Redis、Docker 与网络答案

本页把数据库原理与当前项目实现分开说明。引用已有测试仅表示其覆盖意图，本轮不启动 Docker、数据库或模型调用，也不把历史运行写成当前结果。

<a id="q250"></a>
### Q250：为什么Agent业务数据用PostgreSQL，而向量库用Qdrant？

★ 核心题

#### 1. 标准答案

订单、退款、会话、确认和幂等记录需要关系约束、事务、可审计状态与精确查询；PostgreSQL 适合做业务事实来源。Qdrant 面向高维近邻检索与 payload 过滤，负责寻找候选 chunk，不应靠相似度决定订单归属、交易状态或权限。两类存储可以组合，也可在其他规模下评估 PostgreSQL 向量扩展，选择依据是检索能力、运维复杂度及一致性需求，而不是“关系数据库不能存向量”。

跨 PostgreSQL 与 Qdrant 没有天然的同一事务。需要 SQL 版本/状态作为权威、向量携带租户与修订信息、检索后再次校验；异步更新场景可设计 outbox 与重建，但不能把候选方案说成已有组件。

#### 2. 面试口述版

我按事实存储和检索索引分工。订单状态、退款、确认与幂等记录必须精确查询并在事务里保持一致，所以交给 PostgreSQL；Qdrant 返回语义相近的文档候选，不能替代业务状态或权限判断。项目私有知识检索也以 SQL 中的主体和有效版本为准，向量搜索带租户及 chunk 范围过滤，再核验命中是否有效。因此旧向量暂时残留也不能直接成为回答依据。两库不是一个原子事务，失败和重建需要明确设计。当前项目有 PostgreSQL、Qdrant 和 SQLite 离线路径，没有 MySQL 适配器；付费尝试账本的 SQLite 还是独立用途，不能混成业务生产库。

#### 3. Adaptive-RAG实际实现

`OrderRow`、`IdempotencyRow` 与私有文档模型见 [app/repositories/models.py:L15](../../app/repositories/models.py#L15)、[app/repositories/models.py:L109](../../app/repositories/models.py#L109)、[app/repositories/models.py:L135](../../app/repositories/models.py#L135)。`OrderRepository.create_refund` 与外层事务协作，见 [app/repositories/order_repository.py:L62](../../app/repositories/order_repository.py#L62)。`PrivateVectorStore.scoped_search` 约束 tenant_subject 与允许的 chunk_id，见 [app/retrieval/private.py:L67](../../app/retrieval/private.py#L67)；`PrivateKnowledgeRetriever._lock` 要求 PostgreSQL 主体范围，见 [app/retrieval/private.py:L126](../../app/retrieval/private.py#L126)。多实例 Compose 声明 PostgreSQL 16，见 [docker-compose.multi.yml:L3](../../docker-compose.multi.yml#L3)。独立付费账本 `AttemptLedger` 见 [app/providers/paid_budget.py:L111](../../app/providers/paid_budget.py#L111)，不要与业务 Session 混淆。

#### 4. 面试官可能追问

- **追问：向量库有 payload，为什么不能直接当权限库？** 答：payload 会随索引更新而滞后；权限撤销和删除要以可信业务记录为准，并在检索路径落实主体、版本与有效性检查。
- **追问：两库更新一半成功怎么办？** 答：不能假装有分布式 ACID。项目有版本与 SQL 权威校验；若要完善大规模异步索引，可设计持久任务/outbox、重试与对账，但目前未实现通用 outbox 平台。
- **追问：本项目用的是 MySQL 吗？** 答：不是。业务部署配置是 PostgreSQL，开发/离线可用 SQLite；MySQL 相关回答只能说明原理，不能声称有适配或实测。

#### 5. 测试与证据

`test_postgresql_ddl_compiles_all_business_tables` 仅编译 PostgreSQL 方言 DDL，见 [tests/unit/test_p4b_dependency_contracts.py:L27](../../tests/unit/test_p4b_dependency_contracts.py#L27)。`test_qdrant_local_adapter_roundtrip_not_real_service` 使用内存 Qdrant，见 [tests/unit/test_p4b_dependency_contracts.py:L35](../../tests/unit/test_p4b_dependency_contracts.py#L35)。它们不是实际依赖服务、跨库存储事务或线上规模验证，本轮未运行。

<a id="q268"></a>
### Q268：Redis常见数据类型和Agent中的典型用途？

★ 核心题

#### 1. 标准答案

String 适合带 TTL 的缓存、计数；Hash 适合对象字段；List 适合简单队列；Set 适合去重集合；Sorted Set 按 score 排序，适合滑动窗口、排行榜；Stream 带消息 ID、消费组与 pending，适合可追踪消费，但仍需业务幂等。具体用途取决于一致性、持久化和故障恢复要求，不能因为有 Redis 就声称已经具备可靠任务队列或分布式锁。

多条命令之间可能被其他客户端插入，读改写限流需 Lua 等原子机制。Redis Lua 原子执行不意味着不可能超时，也不保证已确认数据永久保存；敏感准入无法确认时应拒绝，普通可重建缓存故障可按 miss 回源。数据结构参考 [Redis data types](https://redis.io/docs/latest/develop/data-types/)。

#### 2. 面试口述版

Redis 的类型要和业务约束对应。字符串加 TTL 适合短期检索缓存，Hash 放字段集合，Set 去重，Sorted Set 适合按时间排序的限流窗口；可靠消费还可以研究 Stream 的消费组，但处理成功确认和幂等要另做。Adaptive-RAG 实际主要用字符串缓存与 ZSET 滑动窗口。限流用 Redis 服务端时间，在 Lua 里清旧请求、计数、决定是否写入，避免多实例先检查后写入的竞态。敏感请求遇到 Redis 故障会拒绝；公共政策缓存读失败则回源。两种降级规则不能混用，更不能因为缓存可以 miss，就让付费模型准入在故障时放行。

#### 3. Adaptive-RAG实际实现

`RedisRateLimiter.SCRIPT` 使用 TIME、ZREMRANGEBYSCORE、ZCARD、ZADD、EXPIRE，是滑动日志窗口，不是令牌桶，见 [app/infra/rate_limit.py:L43](../../app/infra/rate_limit.py#L43)。`allow` 校验返回值并对 fail_closed 抛出不可用错误，见 [app/infra/rate_limit.py:L71](../../app/infra/rate_limit.py#L71)。容器对敏感准入设置 `fail_closed=True`，只有明确离线测试条件可用内存限流，见 [app/services/container.py:L140](../../app/services/container.py#L140)。公共 `RedisRetrievalCache` 用 JSON String 与 TTL，订单查询绕过缓存，见 [app/retrieval/cache.py:L64](../../app/retrieval/cache.py#L64)。项目未实现 Redis Stream 任务消费、Celery 或 Redlock。

#### 4. 面试官可能追问

- **追问：为什么 Lua 中使用 TIME？** 答：统一使用 Redis 时间，避免不同 API worker 本地时钟偏差破坏窗口；随机 member 区分同一时间点的不同请求。
- **追问：缓存故障和限流故障为什么处理不同？** 答：缓存是可重建优化，失效可回源；准入是费用和资源边界，无法确认配额时继续执行会突破约束，因此敏感入口拒绝。
- **追问：Lua 原子就等于客户端超时后没执行吗？** 答：不是。服务端可能执行了但响应丢失；系统对未知准入保守拒绝，可能牺牲少量可用性，不能据超时假定没有消耗窗口名额。

#### 5. 测试与证据

`test_sensitive_quota_errors_are_explicit_denial` 和 `test_sensitive_quota_wait_is_bounded` 分别验证异常拒绝与等待上限，见 [tests/unit/test_p4f_rate_policy.py:L13](../../tests/unit/test_p4f_rate_policy.py#L13) 与 [tests/unit/test_p4f_rate_policy.py:L23](../../tests/unit/test_p4f_rate_policy.py#L23)。缓存故障测试 `test_redis_cache_get_degrades_on_error` 见 [tests/unit/test_retrieval_cache.py:L153](../../tests/unit/test_retrieval_cache.py#L153)。这些使用 fake/mock；旧默认 fail-open 测试不代表当前敏感入口策略，本轮未重跑。

<a id="q286"></a>
### Q286：从浏览器到FastAPI再到DeepSeek API经历哪些网络环节？

★ 核心题

#### 1. 标准答案

浏览器解析目标 URL，通常经历 DNS、连接建立、HTTPS 的 TLS 握手，再发送 HTTP 请求；连接可能复用，并非每次都重新握手。跨源时还涉及 CORS 与可能的预检。请求可经过负载均衡/反向代理，再到 ASGI server 与 FastAPI 路由、鉴权及业务编排。服务端另建或复用到模型供应商的出站连接，携带服务端密钥；浏览器不应直接获得模型密钥。

每一跳都可能发生 DNS、连接、读取、连接池等待或代理超时。SSE 还受代理缓冲、空闲超时和断连传播影响。是否有 TLS 终止、CDN、Ingress、HTTP/2/3 必须依据实际部署说明，不能从一份 Docker Compose 推导出公网拓扑。

#### 2. 面试口述版

我会画两条独立的 HTTP 链路：浏览器到我们的 API，以及后端到 DeepSeek。第一条可能经过 DNS、TLS 和代理，再进入 ASGI、鉴权、路由与 ChatService；第二条由服务端 AsyncClient 调模型，密钥只放在服务端。连接复用时不必每次重建 TCP 和 TLS。项目浏览器用 POST fetch 获取 SSE，后端在模型结果校验后推送答案片段。排障时我会沿 trace 分辨浏览器错误、API 准入、连接池等待和供应商超时。仓库有 Nginx 多实例配置，但不能因此声称当前公网已配置 TLS、代理无缓冲或具备线上 SLA，这些都需要独立部署证据。

#### 3. Adaptive-RAG实际实现

前端 `checked` 拼接 `/api/v1` 并携带认证头，见 [frontend/src/lib/api.ts:L50](../../frontend/src/lib/api.ts#L50)；流式入口为 POST，见 [frontend/src/lib/api.ts:L111](../../frontend/src/lib/api.ts#L111)。API 中间件绑定 trace/request ID，见 [app/main.py:L78](../../app/main.py#L78)。`DeepSeekProvider` 配置独立连接、读写和池超时，POST `/chat/completions` 并在服务端添加密钥，见 [app/providers/deepseek.py:L29](../../app/providers/deepseek.py#L29) 与 [app/providers/deepseek.py:L78](../../app/providers/deepseek.py#L78)。多实例 Nginx upstream 及 proxy_pass 见 [deploy/nginx.multi.conf:L1](../../deploy/nginx.multi.conf#L1)，当前这份配置没有显式 SSE `proxy_buffering off`，也未声明 TLS；不能说这些已验证。

#### 4. 面试官可能追问

- **追问：为什么 curl 快但浏览器失败？** 答：浏览器还有源策略、认证头、混合内容和页面取消等限制；先查浏览器网络面板的实际 URL、预检和响应，再看 API trace。
- **追问：SSE 一直攒到最后才显示怎么查？** 答：分别检查服务端何时 yield、反向代理缓冲和客户端解析；本项目还刻意等待最终校验后才发送答案片段，不能都归咎于网络。
- **追问：模型读取超时会自动重试安全吗？** 答：要看错误类型和预算。已发出的请求可能被计费；重试必须有尝试上限与费用约束，不能无限重试，也不能把模型生成重试套用于非幂等业务写入。

#### 5. 测试与证据

`test_health_and_chat_greeting` 检查 API 与 trace header，见 [tests/e2e/test_chat_api.py:L16](../../tests/e2e/test_chat_api.py#L16)。`test_explicit_non_thinking_mode_reaches_json_and_stream_payloads` 用 MockTransport 验证供应商请求，见 [tests/unit/test_deepseek_thinking.py:L14](../../tests/unit/test_deepseek_thinking.py#L14)。这些不经过公网 DNS/TLS/代理，不证明真实网络 SLA；本轮仅文档审阅，无外部模型请求。
