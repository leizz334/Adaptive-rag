# P4-E 最终工程验收报告

**PHASE_STATUS = PARTIAL_PASS。** Ubuntu隔离工程交付和受限可靠性验证完成；**私有多租户知识库隔离FAIL，因此不是无条件生产安全验收通过**。完整回答语义NOT_ASSESSED，人工包可填写但标签未代填。Experience Active=NO，本阶段新增付费请求=0。

## 范围、版本与审计

从已核验 `71b53b9ab042af75f3dfed1dc46d85a3e2228a27` 创建 `codex/p4-final-acceptance`，复用同一Ubuntu目录、.venv和既有三依赖Compose。没有Worktree/Initializer、生产连接或历史付费重跑。仅新合成订单/会话/探针与新owned项目 `p4b_20261111_p4e_01`。应用最小修复限于 `app/core/security.py`、`app/observability/logging.py`，另外完善README与旧部署页指引。

[PROJECT_FINAL_SUMMARY.md](PROJECT_FINAL_SUMMARY.md)汇总P0–P4-D架构、工程与真实质量；`e0_phase_audit.json`与`e3_audit_reconciliation.json`保留历史状态。原P1-F passes=false/PARTIAL及当时SaaS/uv/network限制没有被强行改PASS。P2真实质量、P3经验收益、C真实任务失败、D微型样本边界继续有效。各阶段旧“禁止下一阶段”只描述当时授权范围，不阻止本次显式授权的E。

## E0：人工语义审核包

[SEMANTIC_REVIEW_PACKET.md](SEMANTIC_REVIEW_PACKET.md)原样展示14个D消融回答和6个D0 HTTP交互，包括问题、历史/Gold条件、实际工具/引用、证据链接和SHA256；[CSV](semantic_review_template.csv)可直接填写事实、完整性、忠实度、业务终态与整体判断。20个来源hash逐项核验。401/400无回答反例应独立核对安全拒绝，不能当自然语言成功样本。所有新人工字段空白；完整语义继续NOT_ASSESSED。没有同模型Judge替代人类真值，也没有把P3七条历史人工标签移用到D。

## E1：安全与可靠性

| 项目 | 结果 | 证据与边界 |
|---|---|---|
| Bearer验证、subject/role/expiry/revocation、伪造/重复头拒绝 | PASS | required-auth真实TCP20项；未授权不调用模型/不写业务 |
| Owner/Session、跨用户业务访问、SSE权限 | PASS（受限场景） | 真实PG/API矩阵；客户端user_id不授权 |
| 应用层Qdrant私有租户过滤 | **FAIL** | 真实adapter丢弃tenant metadata，search无owner/filter；合成sentinel可无owner取回 |
| PG迁移/事务、并发幂等、HITL/replay、全worker重启 | PASS（受限场景） | 13真实依赖+20API/恢复矩阵 |
| SQL写入flush后异常/取消 | PASS | 2新增真实PG测试：订单/审计/幂等一起回滚 |
| Redis TTL/限流/故障恢复 | PASS既定降级；生产严格限流未满足 | 故障时allow-on-error，不称fail-closed限流 |
| 凭据日志与环境错误处理 | 修复后受限PASS | 最终9项针对性；任意无标签secret/第三方handler仍未知 |
| TLS、备份恢复、密钥运营、外部渗透/长时负载 | NOT_ASSESSED | 不属于本次已验证生产条件 |

`evidence/e1_real_FIRST.xml`：53通过（13真实依赖、20真实依赖API、20认证HTTP）；`e1_extra_GREEN.xml`：7通过（2实际SQL中断+5初始日志/PII检查）。最终全量再次涵盖这些测试；重复执行不增加独立样本量。

### 缺陷、RED与最小修复

1. 原ContextFilter只对消息模板做PII masking；格式化Bearer参数、嵌套extra、异常DSN均泄露合成secret。保存 `e1_log_RED.xml` 的3FAIL，日志输出边界增加参数格式化后处理、递归字段与异常输出处理；5目标测试GREEN。没有修改知识库PII清洗语义。
2. fresh-context审查又发现带引号password、JSON文本、mapping消息仍泄漏；新增3反例。还发现demo token先写后chmod存在权限窗口；新增umask022下“首字节写入前FD必须0600”测试。`e3_review_RED.xml` 为4FAIL/3PASS。修复mapping先递归脱敏、引号赋值匹配，以及os.open(O_CREAT|O_EXCL,0600)创建；`e3_review_GREEN.xml` 最终9PASS，审查者只读复核两项important已解决。
3. 真实私有KB探针RED保存 `e1_tenant_RED.json`。这是既有公共KB架构缺少私有租户契约，BM25/vector/cache均共享；只给vector补filter会制造虚假隔离。本次没有声称修复整个ACL系统，明确阻止私有多租户用途。原Qdrant SDK原生filter PASS不抵消该FAIL。未用真实私有数据，也未证明完整HTTP私有KB隔离（该接口契约不存在，NOT_ASSESSED）。
4. Redis故障真实验证fail-open；Bearer仍fail-closed，但付费业务严格配额需要外围gateway/circuit breaker，当前未实现/验收。
5. 独立审查minor：性能表业务相等比较排除了sessions/messages/**pending_confirmations**；原E2限制文字漏写pending。原证据不改写，补充 `e3_independent_review.json` 与本报告；因此性能测试不能证明pending表不变。E1分别验证提案/确认/幂等。

日志脱敏是已覆盖格式的回归保证，不代表任意无标签凭据、外部trace、第三方自有handler或任意生产PII永不泄漏。生产仍应避免记录原始敏感输入。

## E2：部署与恢复

[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)给出新克隆→Python依赖→新owned Compose→迁移→真实app.asgi启动→required Bearer→HTTP/SSE→停机的完整命令；没有覆盖.env。`deploy.py`演示profile显式清付费Key、INFO日志、仓库公共knowledge、关闭Experience/MCP/神经模型，用OfflineLLMProvider；实际三依赖与原FastAPI routes仍真实。不是test-only替代ASGI。

两轮actual ASGI生产设置启动、health/逐依赖ready/capabilities、无认证401、授权SSE answer/done通过：`e2_deployment_VERIFIED.json`。实测capabilities为postgresql/redis/Qdrant、bm25/lexical/offline、degraded=true；不宣称该profile有真实Dense或DeepSeek。第一轮停机oracle错要求exit0，Uvicorn在graceful shutdown后reraises SIGTERM(-15)；FIRST/原日志hash保留，新VERIFIED两轮接受0/-15且检查Application shutdown complete。不是应用业务故障。

三依赖故障/恢复、PG持久化、pending全worker重启与跨worker确认见E1及新API run。镜像ID/digest、Python依赖观察快照及约束文件均保存；**新机器从零安装、独立OCI应用镜像重构建未执行，NOT_ASSESSED**，不能把当前机器复现说成clean-host认证。根docker-compose.yml旧SQLite示例不是这次入口。

## 性能：受控LLM与真实模型分开

固定查询ORD10001状态/金额；1 API进程、真实PG/Redis/Qdrant、controlled LLM、测试hash embed/lexical，无真实神经推理。HTTP/SSE各并发1/4，每格12热请求；另有2首次请求不入热统计。无客户端SQL快照耗时混入请求时延。wall/API CPU/50ms RSS采样和依赖docker stats点采样分别保存。

| 传输 | 并发 | n | 平均ms | P95最近秩ms | 成功rps | 错误率 | API CPU秒 | 峰值采样RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| HTTP | 1 | 12 | 24.54 | 27.99 | 40.70 | 0% | 0.24 | 215.33 |
| HTTP | 4 | 12 | 120.09 | 196.26 | 32.36 | 0% | 0.36 | 215.91 |
| SSE | 1 | 12 | 26.10 | 28.21 | 38.28 | 0% | 0.27 | 215.93 |
| SSE | 4 | 12 | 75.90 | 81.64 | 51.92 | 0% | 0.23 | 216.74 |

48热+2首次请求均成功；业务表比较相等（排除sessions/messages/pending_confirmations）。受控worker启动至健康 2.480s；首次HTTP 58.32ms、首次SSE 29.16ms。这些是进程/应用启动和请求开销，**不是DeepSeek模型冷启动**。

n12且窗口不足1秒/格，不是容量/SLO/soak结果；并发4的HTTP吞吐反而较低，保留原值，不筛选好成绩。CPU只计API进程、采样可能漏短峰、HWM是进程累计，依赖stats为前后点值，不能当请求独立资源因果。原始逐请求SSE/答案/采样在 `e2_performance.json`，不与真实模型统计混算。

### 历史真实模型证据（仅引用，不重跑）

| 阶段 | 请求 | Token | 峰值成本上界USD | 平均模型HTTP ms | P95最近秩ms |
|---|---:|---:|---:|---:|---:|
| P4-C | 36 | 24393 | 0.0093708 | 1549.14 | 3136.39 |
| P4-D | 79 | 45050 | 0.0178215 | 1400.14 | 2056.04 |

仅C+D合计115请求/69443Token/US$0.0271923上界；这是原阶段价格及usage证据，不是当前invoice或项目所有历史账单。E新增真实模型请求0。D真实BGE Embedding进程加载2.861s、CrossEncoder1.021s；已有热IR查询均值Dense30.03ms/Rerank982.48ms（CPU）。没有清空OS缓存，不能叫物理冷机测试；DeepSeek服务器冷启动/不可变权重版本NOT_ASSESSED。

## E3：最终验证

- 修复前全量 `e3_full_FIRST.xml`：863PASS/1历史SKIP；保留，不用它证明后续修复。
- **修复后最终全量 `e3_full_VERIFIED.xml`：867PASS、0FAIL/ERROR、1历史SKIP，102.25s**。既有LangGraph pending-deprecation warning1；未弱化或改Gold。
- Ruff check/format **356文件PASS**；Mypy **150源文件PASS**；`.venv/bin/python -m pip check` PASS。第一静态编排误引用不存在的venv pip脚本，未产出结果；改为python -m pip，启动失败单独记录，不冒充检查成绩。
- 冻结历史214案例：80/80、13/16、30/30、33/33、23/24、22/30、long1/1。原12项非PASS保留；**新增严格PASS→FAIL=0**。修复后新输出ubuntu_E3_verified_legacy_20261111，无历史覆盖。
- API矩阵验证Owner/Session、HTTP/SSE、HITL取消/幂等/并发重放、真实三依赖故障恢复；受控LLM不是新的真实语言质量样本。
- fresh-context独立审查：0critical，初始2important经RED→GREEN解决并复核；1minor作诚实披露。最终全量/交付由执行者验证，不伪称审查者运行过测试。

测试命令（完整环境/run ID及offline网络约束见部署指南）：

```bash
.venv/bin/python -m research.docs.agent_engineering_upgrade.p4_final_acceptance.offline pytest tests research/docs/agent_engineering_upgrade -q
.venv/bin/ruff check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/ruff format --check app tests eval alembic research/docs/agent_engineering_upgrade
.venv/bin/mypy
.venv/bin/python -m pip check
```

## 保留、资源清理与交付

`e3_preservation.json`核对基线所有Git blob，除授权日志源码/README/部署指引/状态文件外不变；历史JSON Gold、报告和C/D ledger原始字节一致。3份D CSV在工作区CRLF、Git LF，经仓库text规范化blob完全相等，未重写或stage历史CSV；不能把行尾归一化误判实验变化。当前E日志源码改变使D旧freeze在当前树上有预期漂移；旧冻结源码仍在D提交，禁止升级旧freeze或据当前E源码重跑旧付费。

`e3_secret_scan.json`检查实际配置API Key、新旧私有manifest凭据及demo token，不输出值；.env/.private/权重/log/db不提交，测试公开synthetic token仅为fixtures。所有实际新增导出文件在stage前再检查。所属3个依赖服务停止、卷保留；API子进程清理有精确PID证据；原有MySQL运行，不prune/down-v或删除任何用户资源。

## 未解决风险与最终判定

- **FAIL/BLOCKED：私有多租户知识库部署**，共享BM25/vector/cache没有端到端ACL。
- **生产限制：Redis故障严格限流未满足**，外围配额/熔断未验收。
- **NOT_ASSESSED：TLS、备份恢复/RPO/RTO、密钥轮换运营、外部渗透/供应链、新主机安装/OCI构建、长时负载/容量。**
- **NOT_ASSESSED：完整开放回答事实/完整性/忠实度、人类整体语义成功率。** 20条审核包待真实人审，既有受限业务PASS不代替语义。
- Memory只有微型受限收益，RAG/Experience总体收益NOT_ESTABLISHED；不强制Experience Active、不新增研究阶段。

工程材料、受限部署与可靠性可交付；上述FAIL/未知决定整体PARTIAL_PASS。正常Push/远程HEAD在delivery.json和Git最终记录核验；最终元数据自身hash以Git/最终答复为准，避免递归。**完成后STOP，Experience Active=NO，不自动启动任何其他阶段。**

交付核验：检查点 `0210248efc4af9bebc32669bcec14d25b6b6eaee` 已正常Push到 `codex/p4-final-acceptance`，git ls-remote与本地精确一致。此后仅补交付元数据并再次正常Push/核验；最终HEAD见Git/最终答复。所有授权工程任务完成，生产验收限制不变，STOP。
