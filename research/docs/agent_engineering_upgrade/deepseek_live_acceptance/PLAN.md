# DeepSeek 真实 Agent 有限验收

Goal: 在现有独立 Real Agent Dev 入口验证真实 DeepSeek，保持正式 Offline 工作台及全部旧数据不变。

Architecture: 保留现有 React/FastAPI/LangGraph/Memory/RAG/Tools/HITL；读取本地 .env 的已配置模型与端点，只将现有 Key 复制到 WSL 原生私有 0600 文件，再通过既有 Compose secret 引用。保留既有持久预算算法，不放宽预留或回收消费。

约束：本轮聚合最多 6 次模型 HTTP 尝试（含重试）、10000 Tokens 保守预留、USD0.05。官方输入/输出峰时上界为 USD0.30/1.20 每百万 Token，使用 deepseek-flash，无供应商搜索/收费工具。无不确定消费时才继续；不足时明确标记未测，不扩大预算。

- D1：核对 .env、变量、模型、价格、DNS/TLS、代理、容器与数据基线；不输出 Key。
- D2：为现代 DeepSeek 配置可选非思考模式，以适配现有短 JSON 输出上限；Real Dev 禁止自动重试。MockTransport RED→GREEN，预算门禁先验；独立8001健康与Provider核验。
- D3：按顺序进行问候、订单、Memory、RAG、异常；每步比较持久账本和 Trace。现有图一轮可能含分类、规划、生成、Faithfulness等多次HTTP；不保证五轮能在六次/10000预留内完成，不能关闭安全节点来制造通过。
- D4：必要最小修复及相关HTTP/SSE回归；停止本轮新建的RealDev服务，保留全部数据与账本；报告真实结果、提交、普通Push和远端HEAD核验。

恢复约定：若持久账本已有 pending/uncertain 或额度不足，停止新增付费调用；不得创建新账本重置预算。本轮已存在025f8b9交付与Git恢复对象库继续保留，不重新初始化项目、不新建Worktree。
