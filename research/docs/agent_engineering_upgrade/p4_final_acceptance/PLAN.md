# P4-E 最终工程验收执行计划

Goal: 在当前Ubuntu工作目录交付可复现的工程验收及诚实的质量/生产风险边界。
Architecture: 复用当前FastAPI/LangGraph、PostgreSQL/Redis/Qdrant与已审计的P4-B隔离sandbox和controlled LLM。E仅新增审计、测试、部署/性能runner与文档；发现可局部修复缺陷时先保存RED、最小修复并回归。不得将公共知识库原型直接宣称多租户私有知识库。
Tech Stack: Python .venv/FastAPI/SQLAlchemy/LangGraph/Docker Compose。
Spec: 本阶段用户P4-E0—E3需求；AGENTS.md。

## Global constraints and rulings
- 基线71b53b9ab042af75f3dfed1dc46d85a3e2228a27，新分支codex/p4-final-acceptance；不建Worktree、不重初始化。
- 不覆盖.env、用户文件、历史Gold/报告/结果；仅新合成数据和新所属Compose项目。
- 不新增付费请求，Experience Active关闭；外部网络在测试worker中禁止；真实LLM统计仅引用既有证据。
- E0只生成新的可填写packet，不代填人工标签；语义NOT_ASSESSED。
- Review focus: 公共KB误称租户隔离；异常/格式化日志泄密；写入中断事务；Redis fail-open限流风险；SSE并发及热/冷测量混淆。
- Ruling: 用户已要求自动连续执行并退出确认提问；原生逐任务执行，复用feature-list/progress作持久ledger。最终按executing-plans安排独立只读whole-branch review。

## E0 工程证据与语义包
- [x] 审核P0–D状态、报告及原始来源hash，区分PASS/PARTIAL/NOT_ASSESSED。
- [x] 原样导出D14+基线6条记录为Markdown和空白CSV；验证来源和20条完整性；更新状态/commit。

## E1 安全与可靠性
- [x] 新owned manifest/Compose项目，迁移并运行现有真实依赖13、API恢复20、认证20矩阵。
- [x] 新探针验证应用层Qdrant租户边界、日志secret保护、并发业务写入/回滚；发现缺陷先RED后最小修复，复杂未覆盖生产条件明确FAIL/BLOCKED。
- [x] 保存安全风险矩阵及RED/GREEN，验证后状态/commit。

## E2 部署与性能
- [x] 复用Compose建立可复现启动命令，使用真实应用Factory/required auth/实际依赖验证健康与恢复；仅测试辅助worker可用受控LLM。
- [x] 固定合成只读任务，HTTP与SSE各并发1/4、每格12请求，独立记录墙钟延迟、吞吐、错误率、进程CPU/RSS；不以客户端快照耗时代替API耗时。
- [x] 记录进程启动、首次请求、热请求；现有真实neural/DeepSeek统计独立引用，不与mock混算。保存host资源/依赖镜像版本；状态/commit。

## E3 最终交付
- [x] 完善README/DEPLOYMENT_GUIDE/PROJECT_FINAL_SUMMARY/架构及LangGraph文档/RECOVERY/最终报告。
- [x] 全量pytest tests+research、Ruff check+format、Mypy/pip及冻结legacy214，独立review、scope/secret/ledger审计。
- [x] 六项边界明确：公共KB租户隔离、Redis失效限流、生产TLS/备份/灾难恢复、真实模型语义、性能适用规模、Experience当前资格。
- [x] scoped commit/normal push/exactlsremote；记录delivery元数据再次正常push核验最终HEAD，STOP。
