# P4-F 安全修复设计与执行计划

用户明确要求连续执行；复用工作树和.venv，无额外设计确认。采用writing-plans、TDD、executing-plans；feature-list/progress是持久ledger，最后独立只读review。基线a081291f9665f39fccb590600d51918773869906。

## 固定架构决策

1. 私有模式显式 `KNOWLEDGE_MODE=private`；默认public保持既有公共语料兼容。private只允许required-auth，且必须真实PostgreSQL/Qdrant/Redis；缺失依赖拒绝，不回退共享语料。身份范围等于服务端认证subject，不支持客户端tenant_id或user_id指定范围，不提供跨subject管理员豁免。本阶段不声称组织内共享/委托管理。
2. 新SQL表private_knowledge_tenants和private_knowledge_documents为权限/版本权威；每租户generation行用于共享读锁/独占写锁。查询在同一请求事务持有读锁，更新/删除/重索引持写锁直到commit，授权以事务快照为线性化边界；已生成的网络/SSE响应可在删除完成后继续送达，不承诺撤回在途字节。文档分块与Chunk metadata携带subject/document/revision，chunk ID包含这三者哈希。
3. 私有BM25仅从当前subject SQL文档构建。独立Qdrant私有collection写入tenant_subject/revision，查询同时过滤subject与当前有效chunk IDs；结果重建自SQL权威chunk，不信任payload文本。Hybrid/RRF、rerank、Graph最终引用只使用已授权chunks。public与private不混合。
4. Redis缓存key包括schema/subject hash/generation/查询/top_k/模式；缓存值经SQL权威chunk验证/重建，异常缓存丢弃。更新/删除/reindex使generation递增，旧缓存与旧vector不可见。Qdrant先写后SQLcommit可产生orphan但不会授权；SQL为逻辑删除权威，物理清理只作用当前subject+document+旧revision，避免取消后的后台删除误删新版本。孤儿向量不含原文且不被SQL授权；物理垃圾回收/备份擦除不是本阶段承诺。
5. 私有文档HTTP CRUD/reindex/search仅认证subject授权，schema禁止额外tenant/user字段；跨subject doc ID返回相同404。内容/文档数量有界，无任意文件路径/外部URL读取。查询API返回授权chunk及其引用；chat工具、Self-RAG与重排复用同一private retriever及请求DB身份。
6. Redis限流改为server TIME+Lua原子窗口/唯一请求member。生产chat（含SSE/确认）及私有KB操作一律fail-closed，超时/断连503，配额耗尽429。健康/ready/capabilities/metrics不依赖业务quota；只读admin catalog仍需认证。远程Embedding启动入库也必须先获得Redis准入。测试用离线无Redis且无DeepSeek/Embedding凭据时仅允许明确testing环境本地限流，不能称全局配额。配置Redis但故障不得回退本地。
7. 不新增付费请求/依赖模型/Experience Active，不修改.env/历史Gold/raw。旧公共read-only Redis utility的显式fail-open测试保留；运行时敏感入口强制closed。旧B3 API Redis故障期望要强化为拒绝，保留旧来源与RED，不改原始结果。

## F1 ACL任务
- [x] 新有界schema/SQL迁移/私有retriever/API及chat请求身份绑定；先新增攻击/缺失配置RED。
- [x] 真实双subject：同文档ID、相似查询、BM25/Dense/Hybrid、cache hit/污染、rerank/citation、CRUD/reindex/重启/并发更新，任何步骤缺身份明确拒绝。
- [x] 状态/证据/任务commit。

## F2 Redis任务
- [x] 原子global限流、503错误契约和生产装配；先RED再GREEN。
- [x] 真实断开/超时/恢复、两进程竞争同quota、HITL写入拒绝与无模型调用；只读探针继续健康。
- [x] 状态/证据/任务commit。

## F3 最终任务
- [x] 全量真实依赖HTTP、pytest/Ruff/Mypy/pip/legacy214；故障原证据保留。
- [x] 独立review；最小修复RED/GREEN、必要最终回归；文档/恢复/secret+scope审计。
- [x] 正常commit/push/lsremote核验；最后元数据正常push核验HEAD；停止，无P5。

## Review focus
认证subject不得被body/header覆盖；旧向量/缓存/多worker词法索引不得复活已删文档；异步任务/工具不得丢身份；Redis检查与写入必须原子且超时拒绝；跨租户异常不得降级公开访问。

## 接入与故障策略

- 生产入口仍为 `uvicorn app.asgi:app`。设置 `APP_ENV=production`、`AUTH_MODE=required`，通过受保护的服务端凭据注册表供给subject/roles/expiry；禁止使用测试fixture token。
- 使用现有Compose私有manifest提供真实 `DATABASE_URL` / `REDIS_URL` / `QDRANT_URL`，运行additive migration `alembic upgrade head` 到0004。仅对新隔离数据库执行迁移roundtrip，绝不降级已有业务数据。
- `KNOWLEDGE_MODE=private` 启用隔离知识库；默认public只允许公共、非敏感语料。private不会导入本机共享knowledge目录，也不会使用public collection/cache。private缺PostgreSQL/Qdrant/Redis配置或未验证身份会拒绝/启动失败；配置Redis但暂时断连时保留客户端，API503，恢复后重新准入。
- `POST /api/v1/knowledge/documents/{document_id}` 创建、`PUT`更新、`DELETE`删除；`POST /knowledge/reindex` 仅当前subject；`POST /knowledge/search` 的query/top_k/mode只选择当前subject授权语料。body额外tenant_id/user_id拒绝422；外部header不能更改scope；不存在/外租户更新删除统一404。单文档10000字符、每subject100文档；没有任意路径/URL读取。
- 同一query的mode可选bm25/dense/hybrid，随后经原DocumentReranker；chat/SSE/知识工具/Self-RAG复用相同scoped retriever。最终引用只能来自SQL权威chunks，模型伪造引用ID不能扩展范围。
- 所有生产chat、SSE、确认与KB读写共用 `rl:closed:v1:user:{subject}` Redis窗口；Lua服务端TIME，UUID成员，accepted-only计数，全局跨worker原子准入。耗尽429；错误/超时/未知返回503 `RATE_LIMIT_UNAVAILABLE`。SSE已发送响应头时通过error/done事件明确失败，没有answer；不是伪成功。
- 限流fail-closed发生在准入边界；不承诺Redis在已准入操作中途失败时撤销整个操作。远程Embedding启动入库另有bootstrap全局准入，避免启动时绕过费用保护。该quota不是Token/美元预算系统。
- `/health`、`/ready`、`/capabilities`、`/metrics` 为只读诊断，无敏感工作准入；ready的数据库硬依赖语义仍在，必须检查各dependency详情。只读admin工具catalog仍需Bearer/admin。Redis缺失时不能把process-local quota称为分布式。
- 唯一local limiter例外：显式testing、public、未配置Redis、DeepSeek/Embedding凭据均空。ordinary-read Redis utility保留显式fail-open用于非敏感调用/旧兼容测试；生产chat/KB不存在该调用路径。不要通过testing模式或空Redis绕过生产准入。

## 验证运行方法

复用 `.venv` 和项目现有sandbox；必须选择新owned项目并检查owner标签，不接触已有用户资源。本阶段实测manifest为 `../p4_dependency_integration/.private/p4b_20261111_p4f_01/manifest.json`（本机私有，不可提交）。

```bash
export P4B_RUN_LIVE=1
export P4B_MANIFEST="$PWD/research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/p4b_20261111_p4f_01/manifest.json"
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox up
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline pytest tests research/docs/agent_engineering_upgrade -q
.venv/bin/ruff check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/ruff format --check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/mypy
.venv/bin/python -m pip check
```

已有测试结果不要直接覆盖；B/A helper需新的P4_E2E_RUN_ID/P4B_AUTH_RUN_ID/P4B_API_RUN_ID，F runtime每次创建UUID run目录和独立合成subject。恢复时读已有证据，不能盲目重跑已完成任务或付费实验。真实依赖验证使用actual ASGI、生产认证/配置和OfflineLLM、受控hash向量/lexical reranker，不冒充神经语义质量，也没有外部付费请求。

## 保留的边界

- 认证subject就是命名空间；未实现组织tenant成员管理、跨subject分享/委托或管理员全租户读取。
- SQL事务快照决定授权；已保存的同owner历史回答、客户端已接收内容、在途SSE不可被后续删除撤回。
- SQL为权威；索引部分失败不会授权孤儿revision。取消的旧revision清理若与同revision重索引交错可短暂影响Dense可用性；等待在途清理完成后显式重索引恢复，不称为泄露或自动重放业务写入。
- 逻辑删除与当前revision物理删除通过；孤儿向量垃圾收集、WAL/备份介质擦除不是本阶段承诺。
- Redis超时准入可能已计数但未执行工作，保守占用quota；不自动重试未知结果。Redis持久化丢失/跨机灾难恢复/SLO另行验收。
- 本阶段不认证TLS/外部渗透/运维密钥轮换/宿主机与数据库管理员威胁；保持P4-E所述生产外围限制和完整回答语义NOT_ASSESSED。Experience Active=NO，无P5。
