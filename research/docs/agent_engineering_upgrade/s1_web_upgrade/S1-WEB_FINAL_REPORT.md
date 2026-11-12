# S1-WEB_FINAL_REPORT

## 最终结论

**PASS（本阶段受控工程演示范围）**。现有 React/TypeScript/Vite 已升级为受认证保护的 Agent 工作台，三类业务演示及额外安全/异常场景均通过真实 Chromium 验证。无新增付费模型请求，Experience Active关闭，未启动S2/S3/P5。

基线 `3fe745c2a77b28075ce77a1f0961381748c00928`；分支 `codex/s1-web-upgrade`。复用固定Ubuntu目录、`.venv`和既有Compose，无新Worktree，无新UI框架/状态库，无Agent/RAG/M2架构重写。最终精确提交及远程核验见delivery.json和Git HEAD。

## 已交付能力

| 项目 | 验收结论 |
|---|---|
| Web-0审计/回答修复 | PASS；实际API矩阵、19个新字段/关联/空退款回归；旧实验/Gold不变 |
| 认证与会话 | PASS；可信本地Bearer → /auth/me，内存凭证/会话，刷新重新认证，无伪生产登录 |
| HTTP/SSE聊天 | PASS；多轮/切换/Markdown/真实节点/校验后分块/取消/120秒超时/网络及SSE错误，无自动重试 |
| RAG与私有知识 | PASS；Owner绑定的列表/文本上传/创建/完整替换更新/删除/检索，实际citation与片段，无客户端tenant信任 |
| HITL | PASS；真实确认、过期/完成状态、撤销、同Action幂等重放、外人404；已执行不能撤销 |
| Agent执行 | PASS；实际LangGraph节点完成顺序、Planner参数摘要、工具状态/有限结果、RAG片段、Memory模式/历史数/摘要使用、真实耗时/TraceID |
| Experience | PASS（只读历史）；来源/失败类型/原则/条件/审核/历史契约及当前未复核状态、E1 Shadow和E0/E1/E2真实对照，NOT_ESTABLISHED明确 |

实际界面：[订单与执行](evidence/workbench_desktop.png)、[Experience历史](evidence/experience_history.png)。截图仅作视觉附件，验收依据是实际浏览器和数据库结果。

## 回答字段丢失修复

S1-EX发现的既有问题：items coverage强制SKU+数量，忽略用户明确请求的名称/定制标志；空退款只粗略查未/无，既漏掉“没有查到”也可能被无关否定误满足。整段safe fallback又只保留SKU/数量，导致真实工具结果中的请求字段丢失。

最小修复位于 `app/agents/goals.py`、`answer_evidence.py`，无需改generate流程：允许工具支持的商品名称标识，按同商品局部语句绑定数量/名称/布尔定制信息；恢复回答保留有界引用名称和明确布尔定制字段；退款空值措辞绑定退款记录。19个新合成回归覆盖跨商品错配、无关否定、错误类型和不同合法措辞。RED11 +关联RED3 +退款绑定RED1证据保留，66相关测试和610unit通过；后续全量934通过。

它仍是保守文本规则，不是完整语义判定器。未修改S1-EX历史评分或重跑付费实验；Experience真实收益仍NOT_ESTABLISHED，既有完整语义人工审核仍NOT_ASSESSED。

## 安全与真实数据边界

使用原Authenticator、Owner隔离、PrivateKnowledgeRetriever、Redis全局fail-closed、持久HITL行锁及原幂等执行器。新增/auth/me仅返回subject/roles；私有列表仅SQL主体过滤；快照只读、按数据库session Owner与生成root共同授权，外人/未知/过期均opaque404。客户端x-trace-id不作为快照主键，不能覆盖其他运行。

Trace不序列化原始State/Prompt/summary/任意工具输入结果或异常文本。参数只允许格式化order_id/sku；结果只允许状态/金额/计数；有限检索片段先脱敏再截断。固定128条/900秒、有界span与字段。所有身份相关浏览器请求绑定凭证scope，切换时中止旧请求，延迟401不能清除新凭证。Token无硬编码、持久化、查询参数或日志。

付费模型请求=0、付费Token=0、费用=US$0。浏览器业务用真实服务和受控OfflineLLMProvider（规则与安全fallback），不是DeepSeek效果评估；网络socket guard额外禁止外部TCP，即使误选provider也不能出站。Hash Embedding/lexical精排是明确的受控夹具，不冒充真实神经模型。

## 验证证据

- 前端：**19 PASS / 0 FAIL**，[Vitest结果](evidence/web5_front_FINAL.json)；`npm run typecheck`、`npm run build`通过。Node22.23.5官方发行包校验SHA，用户目录安装；没有系统环境/.env覆盖。
- 浏览器：**6 PASS / 0 FAIL**，Playwright真实Chromium，单worker、重试0、4.8秒，[结果](evidence/browser_VERIFIED.json)。无page.route/API Mock、无伪造轨迹。包括多轮订单+Memory/工具、HTTP/SSE/会话切换；私有文档全CRUD/引用/跨租户拒绝；取消/确认/幂等；撤销+越权+刷新；Experience与390px响应式；实际断网和传输取消。
- 真实PostgreSQL核验：[业务验证](evidence/business_verification.json)。最终演示ORD95106确认及幂等重放取消审计**仅1条**；各早期独立合成取消也各1次；ORD95104撤销提案后仍paid。没有重置已取消订单来伪造首次成功。
- 后端全量：**934 PASS / 0 FAIL / 1历史SKIP**，184.67秒，[JUnit](evidence/web5_full_VERIFIED.xml)。包含真实PG/Redis/Qdrant、历史HTTP/SSE/认证、多租户/缓存/故障恢复及多进程限流测试。
- Ruff check/format：PASS，**387文件**；Mypy默认app+eval：PASS，**157源文件**；pip check PASS。实际命令和输出见[checks](evidence/web5_checks.json)。
- 历史回归：**214案例，202 PASS，12既有非PASS，0新增严格PASS→FAIL**。没有将历史未通过项改成PASS：[结果](../p4_dependency_integration/runs/ubuntu_WEB5_legacy_20261112/results.json)。

## 原始失败与纠正

1. Web0按RED/GREEN修复字段/关联/退款缺陷，所有RED保留。
2. 新组件初期缺模块与并行开发时尚未完成的Experience组件导致的测试失败保留；不把FIRST当GREEN。
3. 首轮浏览器2PASS3FAIL：测试按钮“更新”实际是“编辑”、成功中文“已取消”而非英文、session拒绝实际opaque400而非403。只修正测试与真实契约对应，不放宽安全检查。
4. 后续重复合成政策导致引用匹配旧同Owner来源；使用每次唯一标题/问题/ID，仍断言本次实际document_id。Trace有3个真实来源时strict locator不唯一，改按本次document_id定位。历史失败原件保留在browser_FIRST/SECOND/THIRD，不修改旧记录。
5. 独立审查指出身份切换后延迟401和Headers后body超时处理问题；新增authrace RED→GREEN，凭证scope中止/代次检查、JSON/SSE读取错误统一安全映射；另有错误信封RED→GREEN。没有不确定操作自动重试。
6. 第一次全量920PASS/13setupERROR：先普通迁移后fixture要求空库回环，项目安全门禁正确拒绝。未删库/伪造marker；保留FIRST XML，另建全新空隔离项目完成真实up/down/up迁移回环，再全量934PASS。

最终独立代码审查无未解决阻断问题；审查是AI代码审查，不冒充人工语义审批。审查后auth/me body错误也统一映射。

## 已知限制

- 当前没有生产登录/发证HTTP接口或安全服务端历史列表恢复；仅本地可信凭证配置。会话/凭证内存保存，刷新后需重新认证，可见历史不自动恢复。
- Trace是单进程15分钟检查快照，重启/worker切换可能404；不是持久分布式可观测平台。Memory只展示实际元数据，不公开summary或假造M3命中。
- KB仅100篇/主体、10000字符/篇，UTF-8 txt/md，更新是完整替换，无正文自动回填或PDF/Word/OCR；无组织共享/委托。删除不能撤回在途/已送达内容。
- 撤销会删除pending行，后续查询为404，不提供持久撤销历史。确认和撤销保持服务端原子安全；传输取消不代表业务回滚。
- 回答coverage仍保守规则，完整语义质量未认证；历史真实Experience收益未建立，当前Web版本经验资格未重验，不能自动在线注入。
- TLS、凭证轮换/真实身份供应商等外围生产条件不在本次受控工程演示验收内。无新增安全放宽。

## 交付与停止

[架构](FRONTEND_ARCHITECTURE.md)、[API集成](API_INTEGRATION.md)、[演示指南](DEMO_GUIDE.md)、[恢复](RECOVERY.md)、[前端README](../../../../frontend/README.md)。本次三个owned项目9个服务guarded stop，9个卷保留、原MySQL继续运行；不清理其他资源。状态文件逐任务更新，正常Push、ls-remote精确HEAD核验见delivery.json。完成后停止，不启动后续阶段。

```text
PHASE = S1-Web
FRONTEND_AUDIT = PASS
CHAT_SSE = PASS
AUTH_INTEGRATION = PASS_LOCAL_DEV_BEARER
SESSION_MANAGEMENT = PASS_MEMORY_ONLY
RAG_UI = PASS
PRIVATE_KB_UI = PASS
HITL_UI = PASS
AGENT_TRACE_UI = PASS_BOUNDED_PROCESS_LOCAL
EXPERIENCE_SHADOW_UI = PASS_HISTORICAL_READ_ONLY
DEMO_SCENARIOS = 3_REQUIRED_PLUS_3_SAFETY_AND_UX
FRONTEND_BUILD = PASS
FRONTEND_TESTS = 19_PASS
BROWSER_E2E = 6_PASS_REAL_CHROMIUM
BACKEND_PYTEST = 934_PASS_1_HISTORICAL_SKIP
RUFF = PASS
MYPY = PASS_157
HISTORICAL_REGRESSION = 214_CASES_0_NEW_STRICT_REGRESSIONS
PHASE_STATUS = PASS_SCOPED_ENGINEERING_DEMOS
UNRESOLVED_ISSUES = DOCUMENTED_LIMITATIONS_NO_BLOCKING_DEFECT
LAST_COMMIT = SEE_GIT_HEAD_AND_DELIVERY
GITHUB_PUSH_STATUS = SEE_DELIVERY
RECOVERY_READY = YES
EXPERIENCE_ACTIVE_ENABLED = NO
```
