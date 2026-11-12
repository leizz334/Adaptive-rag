# S1-EX 最终报告

## 结论

工程验证通过；真实收益 **NOT_ESTABLISHED**，整体 **PARTIAL_PASS**。完成针对性经验优化和真实配对评估，没有证据支持任务成功率提高。完整语义质量 **NOT_ASSESSED**，没有人工审批或人工语义评分。生产 Experience Active 关闭，未启动 P5 或 S1 产品化。

基线：`b88b2cbe584d061418206c9301078ebbd7e8f08e`；分支 `codex/s1-ex-experience-optimization`。付费实验源码检查点 `8615f9c8f8da4cf1b40ba6846b95d1a2ac7e0c4c`，冻结 207 个文件、依赖版本及只读经验数据库；原始记录见 [runs](runs/ubuntu_EX_20261112_01/)、[freeze](freeze.json)、[逐任务表](comparison.csv) 和 [聚合结果](evidence/ex2_results.json)。最终交付提交以 Git HEAD 与 delivery.json 为准。

## 旧经验与实现

旧 3 条经验记录、历史 Gold、C/D 付费账本和原始实验均保留。旧记录不是因为“代码提交改变”就自动失效：原导出仍 NEEDS_REVIEW/UNREVIEWED；独立验证副本绑定旧版本、旧作用域和验证证据，缺少当前精确许可。2026-11-12 检查时尚未到 Nov16 到期日，不能归因于过期。[诊断](evidence/ex0_old_diagnosis.json)。旧经验自动批准数为 0。

复用 ShadowObserver、ExperienceRepository、审核与验证状态机，新增 tool_coverage、plan_contract、answer_coverage 固定原则。仅 verified failure 与可定位证据可提取，未知或单独评分失败不授予资格。前两类历史遗漏来源与合成工具契约错误来源明确分开。兼容检查覆盖工具 schema/risk/description 和 Owner、HITL、幂等、实体绑定功能摘要；只是建议性兼容检查，不是完整行为等价证明，也不能批准经验。

硬过滤先于相关性排序：精确已验证 tenant/user/session、生命周期、审查、独立验证、证据哈希、有效期、目标契约和 hash-bound permit；最多 2 条，E2 无资格即拒绝。Planner-only system 注入不改变工具目录、原有 Owner/HITL/幂等/执行器。生产 Agent/RAG/M2 没有新增运行 hook，Settings 仍拒绝 active。

3 条新原则通过独立 AI 编写的 9 正例、51 负例，共 60 项结构/安全检查；形成 36 个精确作用域副本，不是 36 条独立经验。均 MODEL_REVIEWED/VERIFIED_OFFLINE，只供隔离实验；人工审批数 0，结构检查不等于业务收益或人工真值。

## 公平配对与真实结果

新开发集 2 题、新独立集 2 题，共 4 个完整 E0/E1/E2 三臂配对、12 个业务 HTTP 任务。开发集审核门禁后使用同一冻结版本执行独立集；独立集反转臂顺序。任务、业务初态、空会话、模型配置和评分一致。没有复用旧 Holdout 冒称盲测，独立标签作者是 AI，不是人类。控制台和账本证明并发 1、重试 0、未知请求 0。

E0 不召回；E1 召回并记录但 Planner 提示前后 SHA 相同；E2 每题实际注入 2 条原则，总 8 次原则暴露。三臂工具顺序和参数均一致，未观察到规划改善。

| 指标 | E0 | E1 | E2 |
|---|---:|---:|---:|
| 工具/参数/业务状态执行代理 | 4/4 | 4/4 | 4/4 |
| 冻结有界回答代理（可评分分母） | 2/3 | 2/3 | 2/3 |
| 开发集有界代理 | 1/1，另1题NA | 1/1，另1题NA | 1/1，另1题NA |
| 独立集有界代理 | 1/2 | 1/2 | 1/2 |
| 模型 POST | 20 | 20 | 20 |
| 总 Token | 18,151 | 17,986 | 18,708 |
| 平均每任务 Token | 4,537.75 | 4,496.50 | 4,677.00 |
| 平均 HTTP 延迟 ms | 8,493.526 | 8,307.463 | 8,394.279 |
| 估计费用上界 US$ | .0071895 | .0069969 | .0072990 |

冻结有界分数：D01 全 true、D02 全 NOT_ASSESSED、I01 全 false、I02 全 true。正向/负向转变均为 0。执行代理不能称为完整业务成功率。E2 比 E0 总 Token +557（约 3.07%）；延迟差异不能解释为速度提升，输出遗漏也影响资源总量。独立有效样本仅 2，不能推广总体收益。

### 负向观察和评分边界

独立的事后字段审计发现 **1 个负向变化**：I01 的 E0/E1 最终回答有请求的商品名称，E2 最终回答只剩 SKU 和数量。三个 generate 提示 SHA 完全相同，原始 E2 生成包含名称，后续 coverage/fallback 丢失名称；不能认定为 Experience 的因果负迁移。

既有 `goals.coverage()` 要求 SKU+数量，空退款措辞匹配有限；`generate` 在 conveyed=false 时用 `safe_answer` 替换完整回答，`answer_evidence.verified_facts()` 未保留商品名/定制标志。D02 三臂也均遗漏请求的名称和定制属性。I01 冻结评分对“没有查到该订单的退款单”存在假阴性，保留原分数，没有事后修改 Gold/评分器。I02 的无物流事件不等于完整回答未发货/无运单号。完整事实性、完整性、忠实度继续 NOT_ASSESSED。

上述既有 Agent 回答问题保留为后续产品化风险，本阶段不在付费结果后修改 Agent 或重跑。事后审计与冻结指标分开展示；[独立审计](evidence/ex2_independent_posthoc_audit.json)、[人工审核包](SEMANTIC_REVIEW_PACKET.md)。4 个当前名称遗漏生成新 NEEDS_REVIEW/UNREVIEWED 提案，另存独立 SQLite，无许可且未参加已完成的 E2。没有自动自学习批准。

## 预算与证据

真实 DeepSeekProvider，模型 deepseek-flash，nonthinking、temperature 0、单次输出最多 1024；固定端点。总 **60 POST / 输入49,254 + 输出5,591 = 54,845 Token / US$0.0214854 估计上界**。上限 120/120,000/US$1，余量未使用。每次写前持久化/fsync 记账，先保守预留完整三臂预算，不确定请求不重试。免费认证/模型列表探测不产生推理 Token。

价格使用 2026-11-12 核验的 [DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing/)，输入 cache-miss 峰值 US$0.30/M、输出 US$1.20/M。实际发票、服务端不可变权重 NOT_ASSESSED。请求/usage/prompt hashes/响应与延迟保留于新账本，不混用旧 C/D 请求。检索仅作为固定受控夹具，Hash Embedding/lexical reranker 不代表真实神经检索评估。

## 修复、回归与交付

保留所有 RED/失败证据：新反思族 RED→GREEN；E2 空资格仍派发、种子碰撞未检查、账本 group 锁范围问题在付费前修复；事件采集重复 case 参数 RED→GREEN。新证据引用路径错误的资格失败保留，仅规范化新记录。Experience 特征观察对“分别查”做局部规范化，未修改 Agent 的既有否定解析。分析脚本 digest 序列化错误仅修复后处理，不改变付费输入或评分。

- 全量 pytest：**904 PASS / 0 FAIL / 1 历史 SKIP**，129.60s；[JUnit](evidence/ex3_full_FIRST.xml)。真实 PostgreSQL/Redis/Qdrant、HTTP/SSE、多租户及 Redis 故障历史安全测试包含在内，隔离受控 LLM 回归无新增付费。
- Ruff check 与 format：PASS，380 个文件；Mypy 默认 app+eval：PASS，154 源文件；pip check：PASS。
- 历史 214 案例：202 PASS、12 既有非 PASS，**新增严格 PASS→FAIL 为 0**；[逐组结果](../p4_dependency_integration/runs/ubuntu_EX3_legacy_20261112/results.json)。不把 214 条全部声称通过。
- 独立代码审查未发现阻断级问题；兼容摘要覆盖有限、人工真值缺失、样本小和私有数据库复现限制均保留。
- [架构](EXPERIENCE_ARCHITECTURE.md)、[零付费离线演示](DEMO.md)、[恢复](RECOVERY.md)。演示使用真实已保存 Planner 响应重放，不是新推理，不制造收益。

正常 Push 并核验精确远程 HEAD，见 delivery.json。完成后停止，等待后续 S1 产品化；Experience Active=NO，P5_STARTED=NO。
