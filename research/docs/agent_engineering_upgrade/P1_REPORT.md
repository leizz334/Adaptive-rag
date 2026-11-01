# P1 — Agent Tracing + Evaluation V2 实施与验收

日期：2026-11-01（Asia/Taipei）。分支：`codex/p1-tracing-evaluation-v2`。P0原有七项状态/交付与历史commit逐字核对保留；Initializer未重跑。只实施P1，未开始P2–P4。

**结论：本地实现与离线验收完成；整体阶段为 PARTIAL_PASS。** 真实SaaS连通、真实模型质量/独立裁判人工校准、PostgreSQL并发以及uv解析器检查没有运行，不能据此宣称生产追踪和模型评测全部PASS。保留所有实际失败场景，没有改gold提高分数。

## 交付和执行链

| 任务 | 实现/文档 | 实际检查点 |
|---|---|---|
| P1-A | [基线与契约](P1_A_BASELINE_CONTRACT.md)、eval/contracts.py、eval/baseline.py | `9fe2cd5`；166测试通过，含3个新契约测试 |
| P1-B | [Trace接入](P1_TRACE_GUIDE.md)、观测模块、服务/节点/Provider/检索/工具埋点 | `8090d74`；173测试通过 |
| P1-C | [工具评分定义](P1_EVALUATION_V2.md)、实际Tool事件/参数/轨迹/失败分类 | `2479522`；186测试通过 |
| P1-D | [隔离业务终态](P1_ENVIRONMENT_EVALUATION.md)、SQL环境、Goal oracle、Session归属修复 | `8da4408`；192测试通过 |
| P1-E | [五态Judge与多轮](P1_JUDGE_MULTITURN.md)、冻结14场景、真实失败结果 | `ef8f5d8`；203测试通过 |
| P1-F | 本报告、80场景扩展、审查修复、完整回归/重复性/外部限制 | 本次验收后真实hash写入feature-list；云/真实模型未运行，passes=false保留 |

每项交付后有独立元数据commit记录真实交付hash，避免自引用。完整状态及证据见 [feature-list.json](feature-list.json)、[progress.txt](progress.txt) 和git log。原用户修改的AGENTS.md推送策略、未跟踪文档/图片/脚本/test_10_27均未混入提交。

Trace路径：ChatService轮次根 → session/confirmation → Graph/node → DeepSeek逻辑/HTTP尝试、检索/精排、Tool与Memory → persist/commit → SSE送达/取消。已有trace_id、日志、Metrics保留，响应新增可选root_run_id。默认关闭；开启local只记白名单元数据，LangSmith需独立显式密钥。Provider输入输出、工具参数/业务内容、原始State和异常文字不导出。全State的隐式框架追踪被显式禁用。

评测路径：冻结场景 → 独立合成内存数据库 → 真实ChatService/Graph/Tool/Repository → 本地实际执行事件 → 确定性参数/轨迹评分 + 独立提交终态/读观察oracle → 任务成功。gold只供评分器，不传Provider或Prompt。工具事件与可外发Trace是两个隔离渠道。

## 实际测试与结果

最终完整pytest：**212 passed，0 failed，0 errors**，1条已有LangChain预弃用警告。Ruff check和format对app/eval/tests通过；Mypy对133个源文件通过（非strict，部分未注解函数体不检查）。独立只读审查提出两个重要问题，修复后其定向复查23项通过，无剩余重要发现；最终完整回归包含新增覆盖。

| 离线数据集 | 实际成功 | 环境状态+读观察oracle | Trace开/关与重跑 |
|---|---|---|---|
| 冻结种子14条 | 12/14，85.714% | 14/14，100% | 开两次、关一次，规范化结果一致 |
| 扩展80条（含原14） | **66/80，82.5%** | **77/80，96.25%** | 开两次、关一次，规范化结果一致 |

80条为原14条加66个预先定义的参数矩阵变体，18个场景族；不是80个独立统计试验。扩展前冻结hash：[freeze记录](evidence/P1-extended-dataset-freeze.json)，原14条文件和旧65/100/16条数据未改。扩展矩阵覆盖订单/主体、显式连续查询、取消状态/重放、错误确认/恢复、参数篡改、轮间外部状态变化/显式与指代询问。未因首次结果改标签或次数上限。

失败分类：7例为owner拒绝后fallback重复get_order、超过预先约束的工具次数；7例为历史指代没有触发正确的新工具查询。后者3例还缺少变化后状态的真实读观察，因此环境+观察oracle失败，并非订单被错误修改。失败ID和逐轮理由全部保存在 [最终验证](evidence/P1-final-validation.json) 及原始JSON中。

种子24轮轨迹22轮有效；参数标注轮平均准确率91.667%；实际执行18次、成功率77.778%、1次幂等重放、1次多余调用。执行分母包含故意测试的业务拒绝，不能解释为模型工具选择准确率。Task success同时要求轨迹、参数、预期拒绝/确认及终态硬约束成立，故DB正确不自动算任务成功。

14条样本延迟（包含fixture创建/冷启动）P50/P95最近秩：Trace开run1=266.5/1233.7ms，开run2=219.5/976.8ms，关=237.4/980.4ms。负载小且有冷启动/并行验证干扰，这些只是实际观测，不能据此计算可信Tracing开销、声称开启更快或外推生产SLA。真实模型Tokens/费用未测，离线运行未调用付费模型。

基线A完整166项与最终212项是工程回归比较；没有原始真实模型任务成功率基线，不能把82.5%称为相对旧系统提升。历史MEASURED结果未修改/重算。

## 审查修复与安全回归

1. **实际HTTP/SSE断线清理**：路由显式aclosing，Response在ASGI结束时关闭body迭代器；Trace根作用域放到流拥有的生产任务，队列上限1并等待送达确认，取消时shield清理并等待任务。避免ContextVar token跨上下文重置、悬挂Graph或DB会话。真实ASGI断线、直接路由关闭、普通TestClient SSE和原业务测试均通过。
2. **Goal oracle保留约束**：已有audit/refund/return行被删除或改写也失败；未允许订单、owner/金额、商品/行项目、错误审计目标均不能被“目标已完成”抵消。提交失败测试确认回滚后的状态不能满足取消目标。
3. **导出白名单二次核验**：构造和本地/云序列化边界均拒绝非白名单元数据及非合法引用；合成密钥、手机号、短订单号、嵌套列表、异常文字不在payload。真实LangSmith SDK通过纯离线requests Adapter验证实际POST序列化，不是只断言假Client；没有云端业务数据上传。
4. **Judge错误与空报告**：SUPPORTED/UNSUPPORTED/INSUFFICIENT_EVIDENCE/JUDGE_ERROR/INVALID_OUTPUT严格分类，错误不计幻觉；无有效结果显示N/A而不是0%或崩溃。相对下降要求同一批case的有效判断mask相同，不能只比较相同覆盖率数字。
5. **Session与权限**：已有Session必须归属于给定user_id，确认参数始终使用原审批内容。生产HTTP user_id仍未认证；fixture主体隔离不证明登录安全完成。本阶段没有放宽HITL、owner或写入约束。

新增ruff排除仅指历史审计evidence目录，防格式化/自动修复更改不可变P0证据；新P1辅助脚本另行显式lint/format，app/eval/tests未排除。`sse-starlette`全局AppStatus事件的测试跨event loop污染通过测试局部fixture隔离，不修改库的业务实现。

## 复现入口和证据

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/review-new --junitxml=research/docs/agent_engineering_upgrade/evidence/review-pytest.xml
conda run --no-capture-output -n adaptive-rag python -B -m ruff check app eval tests
conda run --no-capture-output -n adaptive-rag python -B -m ruff format --check app eval tests
conda run --no-capture-output -n adaptive-rag python -B -m mypy
conda run --no-capture-output -n adaptive-rag python -B -m eval.multiturn --dataset eval/dataset/agent_v2_extended.json --output research/docs/agent_engineering_upgrade/evidence/review-offline.json
conda run --no-capture-output -n adaptive-rag python -B research/docs/agent_engineering_upgrade/evidence/p1_control.py check
```

原始结果：[pytest](evidence/P1-F-pytest.xml)、[14条开1](evidence/P1-F-offline-1.json)、[14条开2](evidence/P1-F-offline-2.json)、[14条关](evidence/P1-F-offline-off.json)、[80条开1](evidence/P1-F-extended-1.json)、[80条开2](evidence/P1-F-extended-2.json)、[80条关](evidence/P1-F-extended-off.json)。验证脚本 [validate_p1.py](evidence/validate_p1.py) 核对冻结hash、P0证据、旧数据、规范化结果、原无关文件和实际JUnit；latency、UUID、业务fixture时间不参与确定性相等。

## NOT_RUN、剩余风险及Git

- **真实DeepSeek/独立裁判语义质量、人审一致性：NOT_RUN**。付费模型未授权；离线工具任务结果不能代替线上LLM泛化/幻觉率。
- **LangSmith SaaS连通与账号权限：NOT_RUN**。只通过本地SDK/离线传输和配置验证；默认不开云端，不虚构已上传Trace。
- **uv resolver/lock检查：NOT_RUN**。Conda中没有uv；显式LangSmith依赖沿用已有锁包0.14.7，根依赖和requires-dist最小同步并解析核对，环境0.14.12；未安装升级。后续有工具时应运行`conda run -n adaptive-rag uv lock --check`。
- **生产认证、PostgreSQL并发与幂等、多实例审批、外部MCP写权限、全面日志/存储治理**等P0风险未因本阶段自动消除。真实压力、远程故障及生产部署未验证。
- Git远程核实为`https://github.com/JEen-wang/Adaptive-rag.git`，main为原源码基线，P1目标新分支不存在；读取远程需要网络提升权限。普通连接及push dry-run曾失败（connection reset），尚不能认定具有推送权限。实际推送在本地F交付提交后执行；结果、待执行命令保存在最终状态/进度与push证据，绝不force-push或更新main。没有安装gh或改Git身份/配置。

阶段以PARTIAL_PASS关闭：本地交付、回归和80场景评测可复核，外部未验证项仍明确保留，不设置为全面passes=true。F交付及push结果持久化后STOP，等待P1审核；不得自动启动P2。
