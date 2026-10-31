# P0-F — Security & Engineering Risk Audit

本审计不发送业务请求、不读生产数据、不修改程序。SOURCE_VERIFIED 表示读取源码或测试断言；TEST_VERIFIED 仅用于本次运行的隔离 AST 探针；DOCUMENTED_ONLY 表示注释或历史说明；HYPOTHESIS 表示建议、攻击后果或待测并发影响；BLOCKED 表示受 P0 范围约束没有运行。风险等级是工程优先级判断，不是渗透测试结论。

<!-- acceptance: P0-F.1 -->

## 1. 身份和数据边界

### S01 / CRITICAL：业务身份来自客户端，订单归属校验缺少可信主体

- **证据（SOURCE_VERIFIED）**：[chat/chat_stream](../../../../app/api/routes/chat.py#L15) 仅依赖容器；[ChatRequest.user_id](../../../../app/schemas/chat.py#L21) 可自由填写，默认 anonymous；[_initial_state](../../../../app/services/chat_service.py#L175) 原样写入 State。[GetOrderTool.execute](../../../../app/tools/order_tools.py#L33) 与 [get_visible_order](../../../../app/repositories/order_repository.py#L37) 的确校验订单 owner，但比较对象来自这个 user_id。HTTP 组装处未发现鉴权依赖：[create_app](../../../../app/main.py#L66)、[get_container](../../../../app/api/dependencies.py#L8)。
- **影响**：在接口直接对外且接入真实用户订单的条件下，冒用另一个 user_id 可能读取其订单或以其身份发起确认操作，属于上线阻断级风险。是否存在部署层认证网关以及其是否重写并绑定身份，未检查，不能断言实际部署已经遭越权。
- **已有防护**：订单工具按 owner 隐藏他人订单；SQLAlchemy 参数化查询；订单 ID 输入 Schema。现有 [test_order_is_scoped_to_owner](../../../../tests/integration/test_orders.py#L50) 验证给定 ToolContext 的归属，不验证 HTTP 身份真实性。
- **缺口**：请求字段不等于认证身份；限流 [_enforce_rate_limit](../../../../app/services/chat_service.py#L156) 也使用可变更的 user_id。
- **建议（HYPOTHESIS）**：服务端从已认证 principal 派生 user/tenant；请求体身份不能覆盖它。后续所有 SQL、工具权限、Memory、Trace 关联统一使用此主体；网关假设必须成为可测试部署契约。
- **验证方式**：隔离 HTTP 环境使用 A/B 两个身份，覆盖伪造 user_id、缺失凭据、订单读写、限流换号；期望拒绝且数据库无变化。本次真实访问测试 BLOCKED，未尝试获取他人数据。

### S02 / HIGH：Session ID 没有 owner 校验，可混写会话

- **证据（SOURCE_VERIFIED）**：[SessionRepository.get_or_create](../../../../app/repositories/session_repository.py#L15) 已存在行不检查 user_id；[recent_messages](../../../../app/repositories/session_repository.py#L23)、[append_message](../../../../app/repositories/session_repository.py#L33)、[save_summary](../../../../app/repositories/session_repository.py#L39) 只按 session_id；[服务层](../../../../app/services/chat_service.py#L170) 连续调用上述方法。
- **影响**：已知另一会话 ID 时，源码路径允许跨主体读取历史到 State、追加消息/覆盖摘要。当前普通生成没有使用历史，不能据此宣称历史已被模型泄露给响应；污染持久化和后续接入历史后的泄露风险仍成立。
- **已有防护**：自动生成 Session ID；[SessionRow](../../../../app/repositories/models.py#L79) 保存 user_id；确认动作另有 user/session 绑定。
- **缺口**：不可猜测 ID 不能替代授权；没有仓储级 owner 条件。[聊天 E2E](../../../../tests/e2e/test_chat_api.py#L14) 未断言跨用户 Session 拒绝。
- **建议（HYPOTHESIS）**：所有会话读写统一按认证 user/tenant + session 授权；违规统一拒绝，不能顺便迁移 owner；新 Memory 功能依赖此边界先成立。
- **验证方式**：A 建会话、B 用相同 ID 读/写/摘要/确认，断言拒绝且 A 数据逐字不变；多轮/长期记忆亦同。本次仅源码核查。

## 2. 工具、审批和业务状态

### S03 / MEDIUM：HITL 已有绑定，但审批记录只存在进程内

- **证据（SOURCE_VERIFIED）**：[_pending_actions](../../../../app/services/chat_service.py#L61) 是字典；[_resolve_confirmation](../../../../app/services/chat_service.py#L191) 检查存在性、15 分钟期限、session/user；[_remember_pending](../../../../app/services/chat_service.py#L204) 存储并惰性清理。确认后 Planner [复用原始工具和参数](../../../../app/agents/nodes/planner.py#L169)，不是根据第二轮文字重新决定写入。
- **影响**：多进程、重启或请求到另一实例可能丢审批、返回不存在；反复确认不会在这里消费审批，要依赖下游幂等。身份伪造风险属于 S01，不能重复计算为“完全没有 HITL”。
- **已有防护**：[test_confirmation_is_bound_to_session_and_user](../../../../tests/unit/test_action_confirmation.py#L45)、[显式提案测试](../../../../tests/unit/test_action_confirmation.py#L25) 存在；[executor](../../../../app/agents/nodes/executor.py#L104) 在提案未确认时跳过执行。
- **缺口**：缺少可恢复的审批状态、原子领取/消费、多实例期限一致性；现有测试不是断线/跨实例审批测试。
- **建议（HYPOTHESIS）**：审批记录与主体、参数摘要、风险、期限、版本及执行结果绑定；状态持久化并定义重放语义，确认前重新核验业务前提。
- **验证方式**：隔离环境跨实例确认、过期、重启、改参数、用户拒绝和重复确认；统计误写率、审批丢失率。未运行。

### S04 / HIGH：幂等有顺序去重，尚不能证明并发和业务去重

- **证据（SOURCE_VERIFIED）**：[executor](../../../../app/agents/nodes/executor.py#L130) 先 get、执行工具、再 put；[IdempotencyRepository](../../../../app/repositories/idempotency.py#L16) 查询后插入；[IdempotencyRow](../../../../app/repositories/models.py#L109) 仅 key 主键，无主体或业务唯一约束。[_fingerprint](../../../../app/agents/nodes/executor.py#L42) 根据工具与参数生成。
- **影响（HYPOTHESIS）**：同 key 并发竞争、不同 action_id 对同订单重复申请、写入后重试需区分；不能把数据库主键冲突自动等同重复副作用，事务回滚可能阻止重复提交，但当前未测其行为。远程副作用更不受本地回滚保护。
- **已有防护**：正常确认优先用服务端 action_id 作 key，payload 冲突返回 409；同事务写业务/审计/幂等，ChatService 最后 commit；[顺序幂等集成测试](../../../../tests/integration/test_orders.py#L34) 有单条退款断言。
- **缺口**：该测试手动一次 create_refund 后读取幂等记录，不是并发完整工具重放。全局 key 命名也不适合作为未来多租户边界；正常确认路径优先 action_id，不能直接推断任意用户指定 key 已造成跨用户响应泄露。
- **建议（HYPOTHESIS）**：将主体、operation、参数摘要纳入幂等协议；在数据库约束和状态转换上定义业务唯一性，远程写服务提供自身幂等；明确失败与成功记录、过期/重试规则。
- **验证方式**：独立临时数据库屏障并发同 key/不同 key、冲突参数、崩溃/回滚、远程超时；检查最终业务记录、审计和返回一致性。并发验证 BLOCKED，本次未连接数据库。

### S05 / HIGH：退款/退货写入的业务前提与取消并发语义不足

- **证据（SOURCE_VERIFIED）**：[退款工具](../../../../app/tools/aftersale_tools.py#L79) 检查 owner；[create_refund](../../../../app/repositories/order_repository.py#L62) 对存在订单创建全额 requested 退款并改为 refunding，没有资格/状态判断；[create_return](../../../../app/repositories/order_repository.py#L97) 类似创建 requested；[cancel_order](../../../../app/repositories/order_repository.py#L123) 有 CREATED/PAID 判断，但先读再更新，非带前态条件的原子更新。
- **影响（HYPOTHESIS）**：不合法状态申请、重复申请或发货/取消竞争可能造成业务状态冲突。requested 只代表申请，不是退款到账；本审计没有把创建申请描述为付款已经执行。若业务故意允许任意状态提交待人工审核，应明确该契约，仍需约束直接修改订单为 refunding 的条件。
- **已有防护**：owner、显式确认、参数校验、事务、审计；取消有状态检查。[退款持久化测试](../../../../tests/integration/test_orders.py#L90) 检查 requested。
- **缺口**：Prompt 的资格说明不能替代仓储/领域校验；确认等待期间订单可能改变；测试未覆盖完整资格矩阵和竞争。
- **建议（HYPOTHESIS）**：定义申请/审批/执行状态机和当前政策版本；提交时以业务代码检查最新状态，原子保护状态转换；失败不能靠生成器解释成成功。
- **验证方式**：隔离资格矩阵、已退款/已取消/定制商品、重复申请、确认前状态变更、发货竞争，断言受影响行数及数据库终态。未运行。

### S06 / HIGH（条件性）：EXTERNAL 工具未纳入统一写审批

- **证据（SOURCE_VERIFIED）**：[WRITE_RISKS](../../../../app/tools/permissions.py#L7) 仅 WRITE/DESTRUCTIVE；[MCPToolProxy](../../../../app/mcp/adapter.py#L19) 默认 EXTERNAL；[merge_mcp_tools](../../../../app/mcp/adapter.py#L50) 不读取 spec 的操作风险；[call_mcp_tool](../../../../app/mcp/runtime.py#L53) 对配置 endpoint 发 HTTP POST，只验证返回为对象。
- **影响（HYPOTHESIS）**：未来远程工具若有写/披露副作用，将不经过相同确认/幂等路径；POST 本身不证明有业务写入。当前内置两个 local MCP handler 为静态查询，未发现已启用的远程写工具，也没有证据证明用户能控制 endpoint，因此不报告已证实 SSRF。
- **已有防护**：工具注册名称白名单、固定配置 endpoint、10 秒超时、JSON 对象检查；本地静态后端不执行网络写入。
- **缺口**：EXTERNAL 混合了“传输位置”和“操作风险”；无统一的输入/输出细粒度 Schema、主体授权、响应大小和外发字段策略。
- **建议（HYPOTHESIS）**：将 transport 与 effect/risk 分开定义；远程工具按实际权限审批，服务端实现认证、白名单和输出约束；未知风险不默认自动放行。
- **验证方式**：仅使用本地假 MCP 服务，返回恶意指令、超大输出、非对象、超时及模拟写操作，验证审批和外发参数；本次无网络调用。

## 3. 注入、隐私、Memory 和经验

### S07 / HIGH：注入防护依赖有限模式和 Prompt 约束

- **证据（SOURCE_VERIFIED）**：[detect_prompt_injection](../../../../app/guardrails/injection.py#L10) 匹配有限正则；[guardrail_node](../../../../app/agents/nodes/guardrail.py#L9) 只检查 user_query；[ANSWER_SYSTEM](../../../../app/prompts/answer.py#L5) 包含不可信上下文告示；[generate_node](../../../../app/agents/nodes/generate.py#L52) 把工具结果序列化后纳入 Prompt。
- **影响（HYPOTHESIS）**：改写/间接指令、污染知识文档或工具返回值可能误导模型、引用或判断；是否绕过真实模型未验证。faithfulness 检查支持性不构成操作授权检查。
- **已有防护**：输入正则、意图拒答、告示、工具白名单/Schema、写确认、owner 检查、faithfulness；[guardrail 单测](../../../../tests/unit/test_guardrails.py#L9) 与 [HTTP 拒答测试](../../../../tests/e2e/test_chat_api.py#L28) 覆盖明显攻击。
- **缺口**：测试没有间接工具/文档注入矩阵。[test_blocks_weapon_query](../../../../tests/unit/test_guardrails.py#L15) 是独立边界函数测试，不能证明主 Graph 调用了该函数。工具输出没有因包含 banner 而变成可信指令。
- **建议（HYPOTHESIS）**：结构化数据和权限硬约束承担安全边界；上下文标注来源/信任等级，限制工具输出尺寸与允许字段；扩展间接注入、越权/绕确认安全评测。
- **验证方式**：假工具/合成文档离线攻击集，分别统计阻断、误拒和实际未授权副作用；模型验证留待授权沙箱，不能只看拒答关键词。

### S08 / HIGH：现有脱敏不足以直接启用全量 Trace

- **证据（SOURCE_VERIFIED）**：[redact_mapping](../../../../app/core/security.py#L28) 递归 dict 不递归 list；[mask_pii](../../../../app/core/security.py#L42) 仅固定正则；订单正则要求比种子 ORD10001 更长的数字；[ContextFilter](../../../../app/observability/logging.py#L20) 仅处理 record.msg，未覆盖 args/extra/异常。[_persist](../../../../app/services/chat_service.py#L241) 保存原始消息；[MessageRow](../../../../app/repositories/models.py#L89)、[AuditLogRow](../../../../app/repositories/models.py#L99) 无字段级保留/删除机制。
- **影响**：日志、未来 SDK 自动捕获及数据库可能包含订单标识、业务内容、密钥或用户数据。当前完成日志只记录有限元数据，不能据此声称现在已经把全部 Prompt 上传云端；尚未接入 Trace 服务。
- **已有防护**：Settings SecretStr、部分 PII 正则和密钥键脱敏；[test_security](../../../../tests/unit/test_security.py#L5) 测长订单号/字典嵌套。
- **缺口（TEST_VERIFIED，限隔离探针）**：实际函数体证明 list 内 synthetic password 保留、ORD10001 未遮罩、logging 的 `%s` 参数手机号绕过 msg-only 过滤。只用合成内容，不读取真实敏感值。
- **建议（HYPOTHESIS）**：Trace 默认仅允许字段；嵌套对象/列表/异常统一脱敏、截断/散列标识，配置采样/保留/访问权限及删除传播；审批参数审计可以保留受控摘要而非公开原文。先本地验证，再考虑云端。
- **验证方式**：合成密钥/电话/地址/邮件/短订单号/工具嵌套值贯穿 async/SSE/异常，检查导出 payload 和日志均不出现；SDK 特性与部署授权另验。本次仅三个隔离探针，不是全链隐私认证。

### S09 / HIGH（新功能准入风险）：Memory / Experience 污染与跨域召回

- **证据（SOURCE_VERIFIED）**：[消息入库](../../../../app/services/chat_service.py#L232) 不把事实与指令分离；会话归属缺口见 S02；[Qdrant.search](../../../../app/retrieval/vector.py#L122) 无 tenant/status/version 过滤。目前没有正式长期用户 Memory 或 Experience Store，详见 [B](memory_context.md)、[E](experience_memory.md)。
- **影响（HYPOTHESIS）**：若直接复用当前知识 collection 存经验，恶意用户/错误反思可能跨用户传播指令、过时订单事实；这是未来接入的门禁，不是宣称当前已有经验污染事件。
- **已有防护**：当前历史没有进入普通 Generate；知识库是受控文档；没有自动反思入正式 System Prompt 的路径。
- **缺口**：缺少独立经验生命周期、审核/来源/失效与长期用户事实权限模型，不能用当前公共知识检索直接替代。
- **建议（HYPOTHESIS）**：四类数据物理/逻辑隔离；只有验证和审核后的程序性经验可召回，不能存订单快照/PII/特权指令；用户记忆遵守 owner、同意、删除；业务当前状态必须实时读权威库。
- **验证方式**：跨用户召回、撤回后不可命中、过时政策、恶意 lesson、gold 泄漏、负迁移测试；这些为后续验收建议，本次未实现。

<!-- acceptance: P0-F.2 -->

## 4. 评测与运行工程风险

### S10 / HIGH：正式 E2E runner 没有隔离环境强制门禁

- **证据（SOURCE_VERIFIED）**：[eval_e2e](../../../../eval/runner.py#L396) 读取 get_settings、要求真实 DeepSeek key、build_container(seed=True)；[container](../../../../app/services/container.py#L62) 初始化 schema，显式 seed [commit](../../../../app/services/container.py#L128)；每行调用 ChatService.chat，持久化会话并 commit。Settings 默认读取 [.env](../../../../app/config/settings.py#L16)。
- **影响**：错误连接业务库会创建表、补演示数据、写评测会话，真实 Provider 会产生调用费用；未来确认类数据可能引入写操作。当前16条是独立单轮，不提交确认 ID，不能说本次现有数据已执行取消。
- **已有防护**：[pytest conftest](../../../../tests/conftest.py#L5) 设置测试环境、清空模型 key、切 SQLite 和禁外部缓存/向量；[订单集成 fixture](../../../../tests/integration/test_orders.py#L17) 使用内存 SQLite。
- **缺口**：pytest bootstrap 不等于 `python -m eval.runner` 的保护；runner 没有测试库白名单和写能力隔离。conftest 自身也 mkdir data/local，本次禁止在目录外新增文件，因此未直接运行原 pytest。
- **建议（HYPOTHESIS）**：评测必须显式隔离 DB/namespace、假时钟/服务、fixture reset 和外发门禁；在线评测单独授权成本与副作用，不能隐式沿用开发 .env。
- **验证方式**：未来用假非测试 DSN 断言执行前失败，假 Provider 验证无外发；临时 DB 运行完整审批并断言仅 fixture 变更。P0 未运行 runner/TestClient/DB。

### S11 / MEDIUM：缓存/向量索引缺少版本与权限维度

- **证据（SOURCE_VERIFIED）**：[cache_key](../../../../app/retrieval/cache.py#L23) 仅 query+top_k；[订单查询绕缓存](../../../../app/retrieval/cache.py#L18) 是启发式；[Qdrant payload](../../../../app/retrieval/vector.py#L99) 有 policy_version，但 search 不过滤；[ensure_collection](../../../../app/retrieval/vector.py#L79) 只检查存在性不比模型/维度；内存 [cosine](../../../../app/retrieval/vector.py#L18) zip(strict=False) 无维度校验。
- **影响（HYPOTHESIS）**：政策更新后 TTL 内旧值、切换 embedding 后旧索引或维度问题；如未来加入私有知识，现 key/检索接口不足以隔离租户。当前缓存仅公共政策且不缓存工具结果，不能报告已证实私有工具数据缓存泄露。
- **已有防护**：短 TTL 默认60秒、订单启发式绕过、Qdrant stable point ID、policy_version 字段；[cache 单测](../../../../tests/unit/test_retrieval_cache.py#L1) 有现有行为断言。
- **缺口**：无统一 corpus/model/policy/ACL namespace；Redis get 后 [JSON解析](../../../../app/retrieval/cache.py#L74) 在降级 try 外，损坏值可中断请求。
- **建议（HYPOTHESIS）**：明确仅公共缓存的契约或增加身份域；索引/缓存版本化并在政策更新时失效，发布前验证 embedding 身份/维度；坏缓存按受控 miss 处理。
- **验证方式**：假缓存覆盖坏 JSON、跨版本、TTL；临时向量环境切模型/维度/政策；断言不能命中废弃版本。本次未操作缓存或向量库。

### S12 / MEDIUM：限流与 Context Budget 不能构成资源硬上限

- **证据（SOURCE_VERIFIED）**：[RedisRateLimiter](../../../../app/infra/rate_limit.py#L62) 故障放行；内存 limiter [按 key 建字典](../../../../app/infra/rate_limit.py#L29)，key 来自客户端 user_id；[Memory cache](../../../../app/retrieval/cache.py#L36) 没容量上限；[budget](../../../../app/memory/budget.py#L1) 与 [compression](../../../../app/memory/compression.py#L1) 的工具输出预算缺口已在 B 的隔离探针复现。
- **影响（HYPOTHESIS）**：换 user_id 绕单主体限流、Redis 故障时费用/负载放大，大输出突破预期 token预算。实际内存峰值/账单未测。
- **已有防护**：消息4000字符、工具调用/节点步数上限、Provider 超时重试、局部输出压缩；Redis fail-open 为注释中明确的可用性选择（DOCUMENTED_ONLY 的意图，分支本身 SOURCE_VERIFIED）。
- **缺口**：缺少可信主体+全局额度、并发与出站预算；压缩主要在生成后，不能保护已发送的 Prompt；工具上限也未限制每次响应字节。
- **建议（HYPOTHESIS）**：认证身份限流、全局并发/费用预算、降级策略、各来源输出尺寸和生成前 token预算；不要只调大 token_budget。
- **验证方式**：假 Provider/大工具输出、Redis 故障和键基数压力，记录P95、峰值内存、最大Prompt tokens、额外调用数；本次未压测。

### S13 / MEDIUM：SSE 取消、事务与异常观测缺少闭环

- **证据（SOURCE_VERIFIED）**：[stream](../../../../app/services/chat_service.py#L114) 建后台 task；finally cancel 但不 await；数据库上下文覆盖 graph，最终 commit 在 [146行](../../../../app/services/chat_service.py#L143)；guardrail 异常分支 [126行](../../../../app/services/chat_service.py#L126) 提前返回，不走普通 persist/observe；[_observe](../../../../app/services/chat_service.py#L271) 只记录最终 ok/refused，没有全路径异常/span。
- **影响（HYPOTHESIS）**：断线后任务终止/数据库清理竞争、客户端重试已提交但未收到的操作、漏记错误和实际重试费用。cancel 是否造成具体写重复未验证；事务外部副作用无法由 DB 回滚撤销。
- **已有防护**：request_session ContextVar、本地事务、确认幂等；正文在最终 faithfulness 后才发送，避免提前曝光被撤回答案；[SSE 测试](../../../../tests/e2e/test_chat_api.py#L48) 验证 token 拼接等于终答。
- **缺口**：测试未覆盖断线、取消、超时、失败后重试；无明确 committed-but-undelivered 状态和调用级span。
- **建议（HYPOTHESIS）**：统一 terminal status、取消清理和幂等重试语义；Trace 生命周期包含 generator 消费/后台任务和事务结果；未来 Trace 只捕获脱敏数据。
- **验证方式**：本地假 Provider + 临时 DB 在不同节点断开 SSE，确认子任务完成清理、无多余外发、状态可追溯；未运行。

### S14 / MEDIUM：配置、环境和管理员默认值带来复现/部署风险

- **证据（SOURCE_VERIFIED）**：[create_app(settings)](../../../../app/main.py#L56) 用传入设置装路由，但 [lifespan](../../../../app/main.py#L32) 重新 get_settings；[CI](../../../../.github/workflows/ci.yml#L34) 检查 lock 后仍 pip install -e 而非据 lock 同步；D 记录环境 LangSmith0.14.12 与 lock0.14.7 差异；[require_admin](../../../../app/api/routes/admin.py#L15) 非 production 且无 token 时开放工具/skill目录，production 无 token 则禁用。
- **影响（HYPOTHESIS）**：测试覆盖设置和实际容器分离、集成版本不可复现、误以 development 对外暴露管理信息。工具目录不是执行接口，不能把开放 introspection 等同任意业务写。
- **已有防护**：production 管理端无 token 禁用、compare_digest、CI lint/type/test、SecretStr；[testing admin 测试](../../../../tests/e2e/test_chat_api.py#L74) 明确验证测试环境开放。
- **缺口**：生产部署 APP_ENV/token 契约、显式 Settings 传递、实际安装版本与 lock 一致性没有当前运行证明。
- **建议（HYPOTHESIS）**：启动前校验环境契约、固定可复现环境与可观测版本指纹；管理员默认访问策略与业务鉴权分别验证。
- **验证方式**：离线构造不同 Settings 的隔离启动测试、production admin 认证矩阵、锁文件安装版本核对；P0 只读元数据，未安装依赖或启动。

### S15 / LOW：客户端相关 ID 直接进入日志/响应和审计

- **证据（SOURCE_VERIFIED）**：[request_context](../../../../app/main.py#L72) 直接采纳 x-trace-id/x-request-id，没有长度/格式/来源校验；[AuditLogRow.trace_id](../../../../app/repositories/models.py#L103) 长度64；[/metrics](../../../../app/main.py#L120) 无应用级访问依赖。
- **影响（HYPOTHESIS）**：重复/超长 ID 混淆诊断，用户把敏感内容写进关联字段，审计字段/数据库类型行为不一致；Metrics 暴露聚合运行信息。是否对外可见取决网络边界，未扫描部署。
- **已有防护**：无 header 时服务端生成、ContextVar 绑定/清理；Metrics label 未使用任意 user_id/trace_id，避免该类高基数风险。
- **缺口**：关联 ID 被误当可信来源的风险；没有应用级文档化 metrics 暴露边界。
- **建议（HYPOTHESIS）**：服务端 root ID 与经校验的 client correlation 分开；长度/字符集限制，Trace ID 绝不作为认证；Metrics 由运维网络/认证保护。
- **验证方式**：合成超长/重复/含敏感样例 header；确认限长与脱敏且不影响业务权限、指标基数；本次未请求接口。

<!-- acceptance: P0-F.3 -->

## 5. 风险顺序、验收与本次限制

优先解除 S01/S02 的主体与 Session 隔离缺口，以及 S10 的评测环境副作用；否则新增 Memory/Trace/Experience 会扩大暴露面。S04/S05 的幂等/状态语义是可靠 Agent 任务成功判定的前提。Trace 上线先过 S08，经验接入先过 S09；这只是依赖建议，未启动任何工程阶段。

性能与安全指标建议（HYPOTHESIS）：越权/未确认写入/错误终态计数必须为0；单独报告误拒率、并发重复提交数、隐私探针泄漏数、坏缓存降级率、SSE取消后残留任务数，以及同负载下P50/P95延迟、Prompt/Completion tokens、Trace开销、调用次数和峰值内存。风险的“0”是建议门槛，不是本次测得结果；负载与置信区间需后续设定。

<!-- acceptance: P0-F.4 -->

本任务实际执行：标准库读取/AST解析、源码链接行号和哈希核对、修改范围检查，以及 S08 的3个合成输入隔离探针。实际探针和命令结果保存于 `evidence/P0-F-validation.json`，仅它们标 TEST_VERIFIED。读取的测试均未运行，测试文件未修改。所有真实鉴权、数据库并发、恶意模型输出、跨实例审批、SSE断线与生产部署验证均未执行；这些 BLOCKED 项不阻碍只读审计完成，不代表风险已修复。

复核入口：[audit_control.py](../evidence/audit_control.py)、[状态](../feature-list.json)、[追踪审计](tracing.md)、[评测审计](evaluation.md)。本报告没有为验证风险而调用真实订单工具、LLM 或外部服务。
