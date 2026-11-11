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
- [ ] 新有界schema/SQL迁移/私有retriever/API及chat请求身份绑定；先新增攻击/缺失配置RED。
- [ ] 真实双subject：同文档ID、相似查询、BM25/Dense/Hybrid、cache hit/污染、rerank/citation、CRUD/reindex/重启/并发更新，任何步骤缺身份明确拒绝。
- [ ] 状态/证据/任务commit。

## F2 Redis任务
- [ ] 原子global限流、503错误契约和生产装配；先RED再GREEN。
- [ ] 真实断开/超时/恢复、两进程竞争同quota、HITL写入拒绝与无模型调用；只读探针继续健康。
- [ ] 状态/证据/任务commit。

## F3 最终任务
- [ ] 全量真实依赖HTTP、pytest/Ruff/Mypy/pip/legacy214；故障原证据保留。
- [ ] 独立review；最小修复RED/GREEN、必要最终回归；文档/恢复/secret+scope审计。
- [ ] 正常commit/push/lsremote核验；最后元数据正常push核验HEAD；停止，无P5。

## Review focus
认证subject不得被body/header覆盖；旧向量/缓存/多worker词法索引不得复活已删文档；异步任务/工具不得丢身份；Redis检查与写入必须原子且超时拒绝；跨租户异常不得降级公开访问。
