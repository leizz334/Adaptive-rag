# P0-E — Failure Reflection / Experience Memory Audit

只研究不训练模型的机制。SOURCE_VERIFIED 表示仓库实际代码；DOCUMENTED_ONLY 表示论文/外部设计或历史文档；HYPOTHESIS 表示下述本项目提案；TEST_VERIFIED 不适用于尚不存在的经验库，当前没有其运行测试；模型调用、训练、数据库改造和E0–E3实验均未运行（BLOCKED）。

## 1. 论文依据与当前能力

<!-- acceptance: P0-E.1 -->

核对的论文为 **Don't Forget What You Just Learned: Self-Directed Repair Turns Agent Mistakes Into Lasting Lessons**，arXiv:2610.31846v1，2026-10-22：[摘要](https://arxiv.org/abs/2610.31846)、[正文 §3.3、附录E.2/F.2](https://arxiv.org/html/2610.31846v1)。论文把失败反思产生的纠正样例蒸馏进LoRA适配器，基础权重冻结，按任务相关性复用适配器。它实际训练额外参数，因此本项目文本经验方案不是论文复现，也不能引用论文增益作为本仓库收益。

借鉴范围仅限“失败→提炼可复用纠正→相关任务选择使用”的反馈闭环。论文还区分分类失败信号与隐藏答案，限制反思获得的评测内部信息；本方案同样不向反思器提供gold答案、隐藏测试或裁判自由文本解释。下面的审核、状态机、SQL存储和文本召回均是本项目独立设计提案，未验证其效果。

SOURCE_VERIFIED：现有 [self_correct_answer:18](../../../../app/agents/nodes/faithfulness.py#L18) 只改本轮无依据回答；[faithfulness_node:100](../../../../app/agents/nodes/faithfulness.py#L100) 将结果留在State.extra；[_to_response:246](../../../../app/services/chat_service.py#L246) 不完整公开这些状态；[models.py](../../../../app/repositories/models.py) 无经验/审核实体；[Skill loader:21](../../../../app/skills/loader.py#L21) 只读取静态业务JSON。不能把Self-RAG、自纠错、session.summary或静态Skill叫成已实现的持续经验学习。

## 2. 四类信息必须隔离

| 信息 | 目的 | 主体与权威性 | 不允许替代什么 |
|---|---|---|---|
| Conversation Memory | 续问、指代、本会话上下文 | 可信owner下的用户/助手交互；内容仍可不可信 | 不能替代业务当前状态或长期授权 |
| Long-term User Memory | 用户同意的稳定偏好 | 单用户/租户范围，有来源、更新、删除和有效期 | 不能把个人偏好当通用业务规则 |
| Experience Memory | 系统执行的程序性改进建议 | 经核验和审核，限定工具/流程/版本/作用域 | 不能代替工具权限、HITL或政策规则 |
| Business Knowledge | 政策/产品规则与其有效版本 | 业务维护者负责；业务事实另查权威工具 | 不能被模型生成的失败反思覆盖 |

SOURCE_VERIFIED 的现有边界：[SessionRow:79](../../../../app/repositories/models.py#L79) 与 [recent_messages:23](../../../../app/repositories/session_repository.py#L23) 是会话；[KnowledgeIngestor:68](../../../../app/retrieval/ingest.py#L68) 是业务知识；[Tool权限:10](../../../../app/tools/permissions.py#L10) 是执行约束；不是可互换的Memory表。用户ID尚不可信，跨用户/全局经验推广必须等身份与租户边界闭合后再开启。

## 3. 不训练模型的闭环

<!-- acceptance: P0-E.2 -->

```text
Trace（已提交、脱敏的可观察执行记录）
 → Evaluation（三态评分 + 业务终态oracle）
 → Failure Classification（带证据的类别，未知单列）
 → Reflection（一次、有界、无工具副作用）
 → Candidate Lesson（不可执行的候选）
 → Verification（反例、版本和隔离回放）
 → Approved Experience（有权审核者批准）
 → Retrieval（先ACL/状态/版本过滤，再相关性）
 → Context Injection（低权限数据块、固定预算、可回溯）
```

1. **Trace/Evaluation：** 输入是观察到的请求、选定工具/安全参数、结果、错误、提交状态和版本，不要求采集模型隐藏思维链。只有经V2确认的任务失败进入内容改进候选。正确安全拒绝、用户取消、等待确认不是坏策略；judge_error、外部服务中断、未知commit只进运维分类，不能自动生成“绕过检查”的教训。
2. **Classification：** 建议类目包括route/coverage/ranking/parameter/trajectory/unsupported_answer/transaction/safety_violation、dependency_failure、unknown。保留源Span和失败证据，类别不等同唯一因果根因；相关性观察不得写成因果事实。
3. **Reflection：** 在授权的离线/异步审核流程中做一次候选提炼，限定输入和输出预算、不暴露业务写工具；可见脱敏轨迹、可观察异常和粗粒度失败类别，不给gold终态/隐藏测试细节。输出失败假设、证据位置、前置条件、适用/不适用范围、纠正建议、验证提案、可能反例与不确定性。只描述短的程序性纠正，不转存原始轨迹或个人信息。
4. **Verification：** 不直接拿失败样本重放成功一次当泛化证明；要有相同机制的独立变体、成功反例、安全负例和错误版本情形。业务终态由代码oracle、权限由规则校验，语义部分经独立裁判/人工检查；结果未知/失败不得批准。验证器保留隐藏gold，不回流反思正文。
5. **Approval/Injection：** 由有权限的人审核并签署不可变版本，发布受控快照；候选、未批准、过期、冲突或撤销经验均不召回。Prompt仅注入所需经验摘要和引用，明确它是有适用条件的参考，不是System政策、用户授权或工具事实。

经验写入不放在当前ChatService事务内；建议未来从已提交Trace引用异步形成候选，避免延长订单事务。审核和发布也不由在线助手自行完成。反思预算不足/经验检索故障时回到E0处理路径，权限与确认规则继续生效；不能fail-open写操作。

## 4. 经验结构、生命周期与防污染

<!-- acceptance: P0-E.3 -->

建议记录（逻辑结构，不是本次创建的数据库表）：

| 字段组 | 关键内容与约束 |
|---|---|
| 身份 | experience_id、不可变version、tenant/scope、类型、owner、内容hash；默认租户内，不根据客户端声明扩大范围 |
| 来源 | source_root_run/call/task/case引用、失败类别、可观察证据hash、生成器模型/Prompt版本；敏感原文留本地受限证据库 |
| 内容 | 简短lesson、trigger/preconditions、exclusions、纠正步骤、反例、不确定性；不含真实订单号/凭证/用户偏好/一次性结果 |
| 适配 | tool/schema/policy/prompt/model/backend版本范围、知识版本、任务域；不支持的版本直接排除 |
| 核验 | 验证集与评分器版本、独立通过/失败数、状态oracle、评审记录、证据覆盖、是否可能依赖隐藏信息 |
| 审核 | reviewer/权限、批准时间/理由、审批签名、发布bundle；生成者不能批准自身候选 |
| 生命周期 | created_at、valid_from/until、last_verified、supersedes、撤销/删除原因、索引版本和失效事件 |
| 使用 | 匿名化的命中、实际注入、采纳/忽略、结果关联、冲突/有害反馈；不以“命中次数多”直接提高权威级别 |

状态建议：`candidate → quarantined → verification_passed → approved → active`；任一阶段可`rejected`；active可`deprecated/expired/revoked`。approved表示审核通过，active表示该版本已发布且可检索，两者分开。版本更新新建记录，不原地覆盖已审计内容；状态变更和评审有独立审计。

**召回：** 从当前任务可用特征和工具需求构造检索，不使用该测试的失败答案或gold；服务端先限制tenant/权限/active/有效期/兼容版本，再词项+语义候选、精排，最多少量经验及固定Token上限（具体K和预算在开发集调定）。无合格经验就不注入。召回后从SQL复核状态/版本，防止向量索引或Redis过期缓存召回已撤销经验。候选相关性分数不是可信度或批准证据。

**去重与冲突：** 对规范化的失败机制、工具、适用条件、版本范围和lesson计算指纹，语义近似只生成合并建议；同一root/重复日志不能当独立支持案例。冲突先缩小scope或隔离审核，不能靠更高相似度覆盖业务政策。发现工具Schema/政策变更、证据撤回、安全事件或人工负反馈时撤销并触发重核验；撤销必须同步SQL、向量和缓存，读取侧再次检查，删除私有来源时处理派生经验的来源合法性。

**污染防护：** 反思输入来自不可信轨迹，统一标注数据边界、脱敏和来源；禁止自动注入未批准候选或自动编辑正式System Prompt。拒绝“跳过用户确认”“关闭owner检查”“把失败请求改成另一个订单”等越权建议。人工批准也不赋予经验更高指令优先级。发布快照可原子回滚；安全回归或命中后负迁移达到预注册门槛时停用bundle，保留证据审计，不让在线使用反馈自动强化错误。

## 5. 组件复用的真实成本

SOURCE_VERIFIED 组件存在；表中新增能力均为HYPOTHESIS，尚未实施。

| 组件 | 可复用处 | 必须补的边界 |
|---|---|---|
| PostgreSQL/SQLAlchemy | 当前[ORM与事务](../../../../app/repositories/models.py)可存结构化经验/评审/版本 | 新的实体、服务端ACL、状态机/并发发布、删除和审计，不混入session.summary或订单表 |
| Qdrant | [QdrantVectorStore:65](../../../../app/retrieval/vector.py#L65)的编码/存储经验 | 当前payload仅业务切片、search没有租户/status过滤；需隔离collection/访问接口，不能直接把经验upsert进cs_knowledge |
| Redis | [cache_key:23](../../../../app/retrieval/cache.py#L23)说明已有短缓存模式 | 经验缓存另namespace，key包含tenant/版本/权限/bundle，失效以SQL状态复核兜底；不能用当前query+top_k共享 |
| LangGraph | [build_graph:45](../../../../app/agents/graph.py#L45)已有明确边界 | 经验召回与Context Builder的受控插入；反思/审核不能变成在线无限递归循环 |
| Prompt/Skill | [Planner:37](../../../../app/agents/nodes/planner.py#L37)已按Skill限制目录 | 参考经验仅建议如何使用允许工具，不扩白名单；经验不是可执行Skill更新 |
| Evaluation / Tracing | [E2E评分:442](../../../../eval/runner.py#L442)、[ChatService.stream:84](../../../../app/services/chat_service.py#L84)有基础结构 | 必须先有可靠失败标签、终态oracle和完整脱敏轨迹；现有启发式不足以自动生产经验 |

## 6. E0–E3 对照与消融

<!-- acceptance: P0-E.4 -->

**E0保留原系统的Self-RAG与本轮答案自纠错。** 这些已存在行为在所有组相同，新增的任务级Failure Reflection不能与原有self_correct_answer混为一谈。

| 组 | 处理策略 | 跨任务持久化 |
|---|---|---|
| E0 | 原始系统，无新增任务级反思/经验注入 | 无 |
| E1 | 任务失败后额外单次Reflection，可在安全隔离重试中用本次教训 | 不持久化、不影响下一任务 |
| E2 | 开发失败中验证/人工批准的固定少量Lessons Prompt，测试前冻结 | 同一固定内容，预算有界，所有测试任务相同 |
| E3 | 从与E2相同批准池按任务召回兼容经验 | 固定池/快照，按需少量注入；测试时不写回 |

固定模型/Prompt/知识/工具/Memory条件；先以M0或同一已选Memory策略运行，避免同时更换记忆产生混杂。主比较使用独立场景族测试集：开发任务产生经验，验证集调K/阈值，测试集不读gold、不创建经验；按同机制未见实体/措辞和跨域/版本变化分层。保存每个run的经验快照、ID/版本、召回/注入记录及无命中原因。

区分三个问题：首次尝试成功率；失败后的恢复率；未来相关任务的重复错误率。E1主要作用于恢复，其未来首次尝试不应因不持久化而声称持续提升。E1额外反思/重试成本必须显式报告；E0原始一次尝试与E1两次尝试的成功率差不能归因于反思。增加**辅助预算匹配对照**：给E0相同重试次数做不反思重采样；各组相同最大执行/工具/模型调用预算，另报告原始E0和成本曲线，不用额外rollout偷换增益。

主指标：任务终态成功、安全违规、同机制重复失败；过程指标：经验precision、无关/过期经验拒绝、负迁移、审核通过率、首次/恢复/未来成功分开、Token/调用/P50/P95/审核成本。统计以完整任务/场景族聚类配对，区间跨零不声称收益；同一个失败派生多个变体不算多个独立证据。辅助消融包括无关/错版本经验（只在合成隔离环境）、乱序/等长填充、禁用经验召回与缺失经验；检查是否只是长Prompt或更多尝试产生收益。

放行建议：确定性安全集零违规、权限和HITL不回退、无跨用户/过期泄漏、失败/取消不重复写入；任务成功增益及允许性能退化阈值待基准后预注册。生产在线经验写回与自动“越用越强”不是本次实验条件，也没有被验证。

## 7. 验证与交付边界

SOURCE_VERIFIED：[test_self_correct_rewrites_unsupported_answer:27](../../../../tests/unit/test_self_correct.py#L27)证明测试代码只覆盖本轮Fake重写路径；[Skill测试:4](../../../../tests/unit/test_skills.py#L4)只验证静态匹配；没有当前经验schema/状态/审批/隔离/撤销/召回测试。上述测试未运行，没有TEST_VERIFIED的经验库结果。

未来验证应覆盖未批准候选不能召回、跨租户/过期/版本不符被拒、向量缓存滞后仍服从SQL撤销、恶意lesson不扩权、独立失败证据不足不批准、评测gold不进入经验、发布/回滚可重现。当前只做引用、源码哈希、依赖已满足、验收段落与范围核查，证据为 `evidence/P0-E-validation.json`。E0–E3、反思质量与经验收益均未运行（BLOCKED/HYPOTHESIS）。仅在Tracing、Evaluation与身份边界闭合后，文本经验方案才具备可评估的工程可行性；不是已实现功能。未启动P3。
