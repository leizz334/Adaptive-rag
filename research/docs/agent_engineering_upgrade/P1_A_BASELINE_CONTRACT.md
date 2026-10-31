# P1-A 基线与评测契约

当前P1分支 `codex/p1-tracing-evaluation-v2`，恢复HEAD `3f789e1`；P0七项状态、报告和证据均逐字匹配其实际交付commit。Initializer未重跑。P0结果文件、数据集及历史报告未改动。

基线快照见 `evidence/P1-A-baseline.json`：原RAG65条、Intent100条、Agent E2E16条，记录原始字节SHA-256及runner/metrics/Checker源码版本。这里只是离线文件快照，真实模型评测NOT_RUN；不以此宣称新成功率。

第一次全量原测试：152 passed、11 errors，均为Windows默认pytest临时目录权限错误，原始JUnit保存在 `evidence/P1-baseline-pytest.xml`。第二次指定临时目录时父目录尚不存在，155 passed、11 setup errors；随后创建审计目录下被忽略的 `.tmp` 父目录，最终 **166 passed**（含3个新契约测试），1条已有LangChainPendingDeprecationWarning。没有跳过失败测试或放宽断言。

验收命令：

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/baseline-fixed --junitxml=research/docs/agent_engineering_upgrade/evidence/P1-A-pytest.xml
```

契约 `eval/contracts.py`：ToolCall保留本地实际工具、参数、执行/拒绝/重放状态、失败类别、轮次；TrajectorySpec分离必需工具、允许集合、等价路径、先后约束和次数上限；EnvironmentExpectation定义订单终态、允许改变的对象、申请数和审计操作；EvaluationResult版本化case、状态、指标、理由、证据和数据集版本。额外字段/非法状态被拒绝；原始工具参数仅供本地评测，绝不直接导出Trace。

确定性评分负责参数、调用轨迹、权限/确认、不允许副作用和提交后的状态。LLM Judge只评价支持性等语义，不作为订单终态或操作授权oracle。模型裁判失败必须独立分类；人工校准和真实模型质量暂未运行。

TDD：新测试首次因不存在eval.baseline而失败；实现契约及只读快照后通过。后续维持原检索指标与原数据文件；新增版本标记而不覆盖旧报告。P0专用验证器保留原样作为历史证据；恢复init.sh只调整为可识别追加的P1任务，不执行初始化。

已知风险：客户端user_id仍非认证身份；不能将隔离fixture身份测试等同生产鉴权完成。AGENTS.md用户新增push规则未提交；无关文档/图片/脚本/测试保持原样。普通远程网络检查失败，阶段末另作安全推送验证，不阻断本地实施。
