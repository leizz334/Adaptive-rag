# API 集成与安全契约

统一前缀 `/api/v1`。浏览器通过 `Authorization: Bearer <内存凭证>` 发请求，不把凭证放URL、正文、存储或日志。无 HTTP 登录/发证功能；本地可信运维可用既有 `python -m app.core.auth` CLI 发证，注册表仅保存哈希。生产 TLS、密钥轮换、身份供应商仍属部署层责任。

| 请求 | 响应/约束 |
|---|---|
| GET /auth/me | 只返回 subject/roles，生产校验，legacy principal拒绝；使用现有限流 |
| POST /chat | message/session_id?/confirm_action_id?/idempotency_key?；服务端绑定主体 |
| POST /chat/stream | SSE started/node/token/answer/done/error；error以机器码处理，EOF无answer拒绝成功 |
| GET /knowledge/documents | SQL subject精确过滤，至多100文档；只返回id/title/revision/character_count，不触发embedding |
| POST/PUT /knowledge/documents/{id} | title/content，已有P4F私有管线；客户端身份字段禁止 |
| DELETE /knowledge/documents/{id} | 当前主体删文档及检索索引，不可越权 |
| POST /knowledge/search | query/top_k/mode(bm25/dense/hybrid)，受保护的 chunks/citations |
| GET /sessions/{session}/actions/{action} | pending/expired/completed及expires_at；主体+session校验 |
| POST /sessions/{session}/actions/{action}/cancel | 同一PG行锁原子撤销未执行提案；完成/过期409，不存在或外人404 |
| GET /sessions/{session}/traces/{root_run} | DB session授权 +内存快照主体/session/root绑定，未知/外人/过期同404 |

新增检查接口均要求已验证身份并沿用 Redis 限流 fail-closed；不使用admin角色绕过Owner。HITL确认走原chat执行器，confirmed action ID作为幂等键；重复提交只读取相同结果，不重复写。取消删除待确认行，不能撤销已完成业务操作；重复取消/后续查询返回404，UI本轮显示已撤销，不声称持久撤销事件历史。

TraceRecorder 的真实span结束后才形成快照。root key为服务端生成，不用客户端x-trace-id作授权或覆盖键。消息/提示/原始参数与结果/内部metadata不直接序列化：仅允许工具order_id/sku格式摘要、状态/金额/计数，检索前240字符按凭据模式脱敏；节点/字段数量、字符串长度、TTL、记录数均有限。Memory不导出实际摘要和历史文本。Tracing关闭或worker切换时可能404，属于明确能力边界。

错误处理：AppError标准error_code/message/trace_id由现有后端返回；浏览器按error_code映射安全中文，不直接展示服务端内部message。HTTP401清凭证，403/404/409/429/503显示明确拒绝；SSE error抛错，Headers之后的超时/网络断开也走安全映射。120秒超时不自动重试，提示可能已提交，先核对状态。人工确认按钮使用相同action进行幂等重放，不生成新键绕过去重。

S1-Web未放宽认证、私有ACL、限流、HITL或幂等检查。受控demo只连本机owned PG/Redis/Qdrant；socket guard拒绝外部TCP，付费providers配置拒绝。
