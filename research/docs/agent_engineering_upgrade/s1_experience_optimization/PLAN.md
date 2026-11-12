# S1-EX Experience Memory targeted optimization plan

Goal: 在P3既有存储/审核/Shadow上实现可验证结构化经验、契约兼容、硬过滤后排序和隔离Planner注入，真实配对如实评估收益。
Architecture: 保留ExperienceRepository/ShadowObserver/FailureAssessment，扩展固定安全catalog，新增兼容与隔离selector模块；实验LLM适配器只在独立research worker调用。Agent/RAG/M2与生产Settings无新hook，ExperienceSettings仍拒绝active。
Tech: 当前.venv/FastAPI/DeepSeekProvider/SQLAlchemy，现有ownedCompose PG/Redis/Qdrant，P3独立SQLite经验存储。
Spec: 本阶段S1-EX用户需求；AGENTS.md。用户要求自动连续执行，免去设计确认；writing-plans/TDD/executing-plans/independentreview。

## Architecture decisions (preserve verbatim)
- 旧3条经验、Gold与raw byte-preserved；失格原因分别列出scope/lifecycle/exactsource/独立验证/permit，不简单以Git变更自动“修复”或批准。
- 新catalog涵盖tool_coverage/plan_contract/answer_coverage，仅VERIFIED_FAILURE+真实证据哈希+结构特征可提取；未知/score-only/评测错误不生成可注入经验。真实历史缺工具来源与合成契约失败明确区分。
- 工具契约manifest包含input schema/risk/description，功能特征包含Owner/HITL/幂等/实体绑定安全机制；兼容不等于批准。源码提交可不同但所需契约/特征必须相同，且每个target仍须独立offline验证和hash-bound permit。禁止给旧记录自动升级。
- 精确tenant/user/session verified scope、lifecycle、provenance、review/validation、compatibility及安全排除先执行，再基于当前任务结构相关性排序，最多2条。当前任务特征只来自请求及工具契约，不使用评分Gold。
- E0无经验，E1只选择/记录、提示字节不变，E2仅隔离Planner system注入canonical原则。可用工具目录、schema、实体绑定、Owner/HITL/幂等以及最终执行器均不变。无合格经验时E2拒绝注入，不能凑对照。
- 新开发2题+新独立2题，3臂同任务/初态/配置/评分/sourcefreeze；每类规模有限，不称总体收益或盲测。独立AI作者标签不是人类真值。先开发、持久reviewgate、再独立；不在结果后调Gold/scorer。
- 120新增模型POST/120000计量Token/US$1/concurrency1/不确定retry0；D/C账本不可动。复用已审计writeahead/fsync/no-replay transport，新EX-onlyledger、整组三臂保守准入；endpoint/model/price不明确即停止付费。
- 官方峰值/cache-miss价格用于上界；temp0/nonthinking/deepseek-flash、每次output<=1024、maxattempt1。服务端不可变权重/实际invoice/开放语义未知保留。

## EX0 diagnosis/extraction/compatibility
- [ ] 旧3条诊断与证据manifest；新source归因分级，RED→GREEN扩展反思catalog。
- [ ] 工具/功能兼容schema和否定测试，兼容不授予注入；状态/commit。
## EX1 independent qualification/matching/injection
- [ ] 新任务/Gold独立作者；验证>=3独立正负/安全反例每经验；existing仓库propose/review/transition，不写humanapproved。
- [ ] selector+relevance+Planner-only injection(max2) RED/GREEN；安全/不匹配/equality/expiry/revocation/sourcechangecounterexamples；新freeze+admissionreview/commit。
## EX2 real experiments
- [ ] 免费models/官方价格/Key存在检查且不输出凭据，建立新owned服务与合成种子。
- [ ] 开发2completeE0E1E2pairs，审核后checkpoint；samefreeze独立2pairs；每HTTP请求持久化账本/Token/latency/decision/tools/business/answers。
- [ ] 整组公平分母、负迁移/零收益/语义NA；状态/commit，不重跑已消费任务。
## EX3 delivery
- [ ] 全量pytest/static/legacy214，失败原证据与必要最小修复；freshreview。
- [ ] S1-EX_FINAL_REPORT/EXPERIENCE_ARCHITECTURE/DEMO/RECOVERY/对照表/人审包；scope/secret/ledger审计、ownedstop。
- [ ] scopedcommit/normalpush/lsremote，最后交付metadata再正常push精确HEAD；STOP等待后续S1产品化，无P5/Active。

## Review focus
没有伪造humanapproval；兼容性不能绕过撤销/expiry；Gold/answer facts不能进入Agent；E1只观察不能改变prompts；E2提示不能增加工具权限或覆盖现有系统约束；未知paid结果必须停。
