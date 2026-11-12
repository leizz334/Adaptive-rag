# Web-0 前后端审计

基线 3fe745c2a77b28075ce77a1f0961381748c00928。复用 React19、TS、Vite、lucide、react-markdown、remark-gfm；已有 Sidebar、Composer、MessageView、SSE decoder、Vitest。当前无浏览器 E2E，Ubuntu PATH 缺 Node/npm，使用用户目录官方 Node22 并校验官方 SHA，不修改系统或 .env。

| 能力 | 当前实际契约 | 处理 |
|---|---|---|
| 认证 | Bearer 哈希注册表，主体由服务端绑定；无登录发证 HTTP | 添加只读 /auth/me，本地开发凭证输入，内存保存，删除客户端演示 user_id |
| 多轮聊天 | POST /chat、/chat/stream，session_id；后端无会话列表 | 复用；浏览器内存会话，身份切换清空，旧 localStorage 不加载 |
| SSE | started/node/token/answer/done/error；最终校验和提交后才发可见 token | 补 error/root_run_id 类型、超时/取消/EOF 错误；不称原始逐Token模型输出 |
| RAG | citations 仅 title/doc/chunk/section | 复用并从受保护的实际 trace 补 allowlisted excerpt，缺失不虚构 |
| 私有文档 | POST/PUT/DELETE /knowledge/documents/{id}，POST /search，/reindex | 复用 JSON 文本入库/更新/检索，增加 bounded 本主体列表；本地 UTF-8 txt/md 上传 |
| HITL | 持久 proposal；confirm_action_id；15分钟；原子消费及幂等 | 复用，增加 owner/session 校验的取消端点；本地取消不能冒充服务端撤销 |
| Trace | TraceRecorder 只向日志/可选外部sink导出元数据，无查询；graph updates 有节点/plan等状态 | 新增 bounded/TTL 只读快照，server-generated key+owner/session；不查询日志/任意路径 |
| Memory | M0/M1/M2；当前上下文/摘要已由服务端选择 | 展示真实计数/模式/摘要使用bool，不导出原始历史/summary或假M3 |
| Experience | 生产仅 off/shadow；S1EX 隔离SQLite，真实收益未建立 | 独立离线合成快照面板，展示原证据，不提供Active/审核按钮 |

安全边界：auth/me 不返回哈希/凭据；private list 不信任客户端主体；Trace key 不使用客户端 x-trace-id；服务端精确 owner/session 授权且 opaque404；只允许有限已知业务字段进入 owner-only trace，不导出原始状态/提示/异常/密钥。内存快照明确单进程TTL与重启丢失限制。

S1EX 回答问题：已有 items coverage 仅 SKU+数量，忽略请求的名称/定制属性；safe fallback 同样遗漏；空退款只按未/无字面匹配，漏掉没有查到。Web0 新独立合成回归先RED，再最小修复 goals/answer_evidence，保持历史Gold/scorer/付费结果不变，详细 JUnit 与修复记录在 evidence/。
