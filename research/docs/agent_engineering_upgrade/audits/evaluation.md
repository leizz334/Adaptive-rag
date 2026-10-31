# P0-C — Agent / RAG Evaluation Audit

本报告只检查评测与设计最小 V2；没有运行正式评测、付费模型或业务数据库。SOURCE_VERIFIED 为当前源码/测试阅读；TEST_VERIFIED 仅指本次隔离 AST 探针；历史结果为 DOCUMENTED_ONLY；建议和未验证影响为 HYPOTHESIS；受约束未运行项为 BLOCKED。

## 1. 数据、指标、调用路径

<!-- acceptance: P0-C.1 -->

入口 [runner.main:564](../../../../eval/runner.py#L564)，支持 intent/retrieval/generation/e2e/all；`all` 只有带 llm 标志才加入生成与E2E。没有 Ragas/DeepEval 的现有依赖或评测调用（[pyproject.toml](../../../../pyproject.toml)）。

| 对象 | 文件与当前规模 | 实际评分与路径 |
|---|---|---|
| 意图 | [intent_100.jsonl](../../../../eval/dataset/intent_100.jsonl)，100条，ID唯一 | [eval_intent_rules:76](../../../../eval/runner.py#L76)、[eval_intent_llm:90](../../../../eval/runner.py#L90)、[eval_intent_overlay:143](../../../../eval/runner.py#L143)：标签相等 Accuracy，覆盖层独立对照 |
| 检索 | [rag_eval.jsonl](../../../../eval/dataset/rag_eval.jsonl)，65条 | [eval_retrieval:166](../../../../eval/runner.py#L166)：BM25/Dense/RRF/CE，P@1、R@3、Hit@1/3、MRR |
| 回答 | 同一65条，含 gold_answer_contains | [eval_generation:287](../../../../eval/runner.py#L287)：无上下文、RAG、RAG+self-check；模型二元判定+全部关键词命中 |
| Agent E2E | [e2e_eval.jsonl](../../../../eval/dataset/e2e_eval.jsonl)，16条 | [eval_e2e:396](../../../../eval/runner.py#L396)：seed=True，逐条 ChatService.chat；规则拒答/关键词/tool_path_hit/延迟 |

数据规模、JSON合法性、ID唯一性与文件摘要由离线验证器实际核对，属于 SOURCE_VERIFIED 数据检查，不是运行模型得到的结果。

检索先经 [_unique_stems:49](../../../../eval/runner.py#L49) 按文档去重，算的是文档级而非切片级指标。[precision_at_k:14](../../../../eval/metrics.py#L14) 用实际返回条数作分母；[recall_at_k:21](../../../../eval/metrics.py#L21) 的相关集合分母不同；[classification_report:46](../../../../eval/metrics.py#L46) 只给按真标签分组的正确率，不是完整precision/recall/F1报表。[percentile:38](../../../../eval/metrics.py#L38) 是排序后取离散位置，16条的P95不能当稳定生产SLA。

线上路径复用并不一致：检索组件单独建内存索引；CE对照召回8条再排5条，而线上SINGLE默认3条并带查询改写；generation用自建Hybrid和_generate_answer，不跑完整Graph，也没启用CE/多跳路由；E2E直接调用ChatService、绕过HTTP/中间件/SSE，且每个样本新建ChatRequest不传session_id。依据：[检索对照:206](../../../../eval/runner.py#L206)、[CE:224](../../../../eval/runner.py#L224)、[生成:299](../../../../eval/runner.py#L299)、[E2E:424](../../../../eval/runner.py#L424)、[retrieval_node:18](../../../../app/agents/nodes/retrieval.py#L18)。

## 2. Agent 能否可靠识别各类失败

<!-- acceptance: P0-C.2 -->

| 能力 | 当前证据 | 判断与缺口 |
|---|---|---|
| Tool Selection Accuracy | [tool_path_hit条件:442](../../../../eval/runner.py#L442) | 没读取实际工具调用，不能可靠识别错工具、该调用却没调用 |
| Tool Argument Accuracy | 同上；[Tool.parse:59](../../../../app/tools/base.py#L59) 做输入Schema验证 | Schema合法不代表order_id/sku/金额/意图正确；评测无参数gold比较 |
| Tool Trajectory | [details:446](../../../../eval/runner.py#L446) 只存意图/策略/拒答/时延 | 无调用序列、step ID、依赖、重试/fallback、审批事件记录；不能评估顺序或多余操作 |
| Environment State Verification | E2E没有前后DB断言 | 不能识别“回答已取消但订单未变”或改错订单。集成测试是局部能力，不是E2E最终状态验证 |
| Agent Task Success | 关键词/ORD/pending启发式 | 提案不等于完成；没有任务级目标谓词、错误分类或终态oracle |
| Multi-turn / Memory | 每条独立请求，无确认后续轮 | 不覆盖指代、跨轮槽位、长历史、摘要、跨会话偏好、删除 |
| Safety | 少量应拒答样本；局部owner/HITL单测 | 无完整越权、间接注入、未授权写入、外部副作用与并发重复操作评分 |
| Latency / Token Cost | 分阶段时延；[生成usage:108](../../../../app/agents/nodes/generate.py#L108) | 其他LLM调用未统一累加，E2E不收集完整Token/费用；无冷启动、缓存、重试、首进度/首正文区分 |

SOURCE_VERIFIED：当前测试支持一些单点约束。例如 [确认参数复用:25](../../../../tests/unit/test_action_confirmation.py#L25)、[用户/会话绑定:45](../../../../tests/unit/test_action_confirmation.py#L45)、[读工具fallback:37](../../../../tests/unit/test_executor_fallback.py#L37)、[订单owner:50](../../../../tests/integration/test_orders.py#L50)、[退款持久化:90](../../../../tests/integration/test_orders.py#L90)。[幂等测试:34](../../../../tests/integration/test_orders.py#L34) 只顺序写一次再读取幂等记录，不是并发重放或回滚故障测试。[API/SSE测试:48](../../../../tests/e2e/test_chat_api.py#L48) 检查事件和最终拼接，不评分业务轨迹。原pytest未执行，不能标成TEST_VERIFIED。

## 3. 已确定的评分口径问题

<!-- acceptance: P0-C.3 -->

1. **tool_path_hit 误判。** query含ORD/库存/取消时，只要回答含任意ORD、任意“库存”或有pending_action就计命中。TEST_VERIFIED：离线执行原函数中提取的评分分支，问题ORD10001、回答ORD99999仍被计为成功。它不是工具选择准确率，也不是任务成功率。
2. **拒答分母遗漏。** [runner:433](../../../../eval/runner.py#L433) 只统计expect_refused为真。TEST_VERIFIED：不该拒答却拒答的样本不会增加该分母或错误数；实际是“应拒答样本的召回”，不是完整准确率。V2要给TP/FP/FN/TN和过度拒答率。
3. **Judge Error 与幻觉混合。** [FaithfulnessChecker.check:52](../../../../app/guardrails/hallucination.py#L52) 把Provider/输出错误映射为supported=false、checker_unavailable；[generation:349](../../../../eval/runner.py#L349) 对所有false计幻觉。TEST_VERIFIED：AST提取实际Checker类配离线失败Stub复现该返回形态；未发模型请求。需要三态supported/unsupported/judge_error，并单报评分覆盖率和失败率，不把未知当事实幻觉。
4. **同模型裁判。** [runner:299](../../../../eval/runner.py#L299) 同一个DeepSeekProvider既生成又传入Checker；`deepseek-faithfulness_v1`是报告标签，不是独立模型版本。相同偏差无法靠temperature=0消除；真实偏差大小未测。
5. **Faithfulness 定义较粗。** [prompts/faithfulness.py:3](../../../../app/prompts/faithfulness.py#L3) 输出样本级布尔值，不逐事实评分；关键词全出现不保证否定、金额和对象正确。无检索组生成不见证据，但评分仍见召回证据，是“与该证据一致”对照而非全世界事实正确率。
6. **副作用与可复现。** [eval_e2e:399](../../../../eval/runner.py#L399) 改环境限流并重取Settings，使用配置数据库、seed=True，ChatService保存消息；不保证隔离真实库。[ingest_to_memory](../../../../app/retrieval/ingest.py#L103) 也可能调用远程Embedding或加载模型。CLI中无llm标志不代表绝对无外部成本。原评测本次不运行。
7. **数据与结果限制。** [MEASURED.md](../../../../eval/MEASURED.md) 历史指标为DOCUMENTED_ONLY，原始JSON未随仓库分发，不是当前重现结果；覆盖规则针对固定短语，需要模板/实体隔离的未见集，不能把固定100条高分升级为泛化证明。

## 4. 最小 Evaluation V2（建议，未实施）

<!-- acceptance: P0-C.4 -->

保留自写runner与pytest，补一份任务级结构化契约，先把成功定义可靠，再考虑框架。每条case包含 case_id/family_id、场景版本、可信身份、隔离环境快照、turns、允许/必需/禁止工具、规范化参数约束、部分顺序/DAG约束、审批条件、业务终态谓词、预期拒答、裁判rubric。允许等价的合法轨迹，不用唯一字符串序列惩罚正确方案。

执行记录建议同时保存 proposed/validated/executed 三种工具事件、执行结果和事务提交事实。通过生产ChatService/Graph运行语义测试；另设少量真实HTTP/SSE协议样本，确保中间件、断流、异常和身份绑定不被绕过。观察接口来自后续Tracing，但测试oracle不能以“trace完整”代替业务正确。

**确定性代码评分为主：**

- Selection：实际执行工具与必需/允许/禁止集合比较，分别报告precision/recall和违规调用；fallback记录原始失败与实际工具。
- Arguments：对order_id、sku、数量、币种和单位等做类型规范化与gold约束；缺失、错误对象、合法但错误值分别计数；不得仅比较Schema通过。
- Trajectory：校验关键先后、结果依赖和确认前零副作用；区分网络重试、工具重试和业务重复写入。
- Final state：独立读取事务提交后的隔离DB，验证目标状态、被影响对象集合、退款/退货条数、审计、幂等与未授权对象不变。与语言回答核对，不能从answer推断DB。
- Task success：必要目标谓词全部满足且无禁止副作用才成功；“正确拒绝不允许操作”可为成功，“等待确认”是pending，不是completed。
- 多轮/Memory：复用受控session与完整turn序列，按任务统计，覆盖M0–M3场景；用户更正、删除、状态变化使用可控环境事件。
- Safety：身份/owner、未确认写、注入、外部输出、缓存混淆与跨用户记忆用确定性不变量；同一用例中允许拒绝，不以流畅答案抵消违规。

**LLM-as-a-Judge 为辅：** 对语义正确性、证据支持、完整性和解释清晰度评分；固定版本化rubric、证据与裁判配置，三态输出，盲化实验组与原系统名称，防止证据中的注入；抽取可核对事实再判。采用独立裁判可减少共同偏差，但不是消除偏差的保证。

**人工校准：** 先用有金标的成功/失败、硬负例和边界案例校准；两名审核者盲审分歧，给出规则与模型裁判的混淆矩阵/一致性。新增经验的批准不能只依赖产生该经验的同一模型自评。

结果需关联task_run_id、root trace/run ID、原trace_id、session/turn、模型和Prompt/知识/工具/记忆/经验快照版本、实际后端、冷暖缓存、seed/采样参数。主指标为任务成功率和安全违规率；同时报告参数正确率、最终状态正确率、重复错误率、judge error、Token/调用/费用、P50/P95、失败/超时/取消。以场景族或完整轨迹作配对统计簇，报告区间、样本数、重试预算；收益阈值未预注册前不承诺百分比。

隔离要求：显式测试配置、独立临时数据库/namespace、禁用真实外部写工具/出站模型调用、只用合成数据；拒绝指向生产配置。仅内存DBfixture存在不等于整个评测入口已隔离。[tests/conftest.py:5](../../../../tests/conftest.py#L5) 会改环境并mkdir，故当前任务不运行原pytest或collect-only。

### 框架比较与工程成本

以下能力依据官方文档，属于DOCUMENTED_ONLY；相对成本是对当前代码的HYPOTHESIS判断，未安装试用。

| 方案 | 当前仓库成本 | 取舍 |
|---|---|---|
| 自写V2 | 最低迁移；补任务/事件契约、DB oracle与报告 | 最适合先解决确定性正确性；需自行维护数据与统计 |
| DeepEval | 中等；映射工具调用和case对象、选裁判和运行模式 | 官方[Tool Correctness](https://deepeval.com/docs/metrics-tool-correctness)支持期望工具及参数/输出严格性；[Argument Correctness](https://deepeval.com/docs/metrics-argument-correctness)提供模型判参。仍不能替代本项目事务终态oracle |
| Ragas | 中等；适配question/context/reference/response与工具样本 | 官方[指标目录](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)含RAG与tool/goal类指标；适合语义/检索补充，但需自建审批和业务状态真值 |
| tracing平台评测/pytest插件 | 依赖已有事件契约和版本记录 | 可统一运行/人工队列；平台换掉不应改变本地硬约束评分定义 |

建议先交付离线确定性V2和三态Judge，再择一引入语义评测适配。锁定候选SDK版本并检查现有Python3.11/3.12与LangGraph0.2依赖兼容；不根据最新文档直接改生产依赖，不默认上传数据，不估造价格/人日。

## 5. 核查结果与限制

SOURCE_VERIFIED：原[metrics单测:63](../../../../tests/unit/test_metrics.py#L63)覆盖基础算术和短列表口径；[自纠错单测:27](../../../../tests/unit/test_self_correct.py#L27)用Fake模型，不校准真实裁判。[CI](../../../../.github/workflows/ci.yml)有lint/mypy/pytest覆盖率门槛，不是业务成功率门槛。

TEST_VERIFIED：实际执行AST提取的metrics、E2E评分分支和Checker失败路径，复现上述误判/错误映射；只在内存Stub上执行。数据65/100/16及ID唯一性由同一离线验证核实，证据保存到 `evidence/P0-C-validation.json`。原E2E、LLM裁判、V2改造和新增实验均未运行（BLOCKED/HYPOTHESIS）；没有把历史100%评分写成当前已验证结果。

验收映射：C.1→第1节；C.2→第2节；C.3→第3节与隔离探针；C.4→第4节比较和最小V2。没有开始P1。
