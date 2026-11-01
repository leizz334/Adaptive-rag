# P1-E Judge 与多轮离线评测

## 五态裁判

FaithfulnessResult新增status并保留supported兼容访问/旧布尔JSON输入。SUPPORTED/UNSUPPORTED是已判断结果；INSUFFICIENT_EVIDENCE独立表示不足；调用异常为JUDGE_ERROR、无效或矛盾JSON为INVALID_OUTPUT。缺证据不调用裁判；错误/无效不会增加HALLUCINATION_FLAGS。旧模型输出supported=true/false仍可解析，但字符串yes、缺字段、矛盾status均拒绝。

`eval/judge_metrics.py` 的hallucination_rate = UNSUPPORTED/(SUPPORTED+UNSUPPORTED)，无有效判断为null；judged_coverage与五态计数必须同时报告。legacy_supported_fraction保留旧supported/n口径；原检索P@K/Recall/MRR未改。生成runner标记deepseek-faithfulness_v2，不把错误计幻觉；不同覆盖率不报相对下降。真实裁判/同模型偏差校准NOT_RUN，代码分类测试不证明语义裁判准确。

## 数据和驱动器

`eval/dataset/agent_v2.json` 是首轮运行前冻结的14个手工标注合成场景；不是用当前输出生成gold，也没有为了得到高分复制到80条。规模扩展至约80条需后续独立标注、评审和场景族拆分，不能把14条称为80条完成。

覆盖：普通查询、提案无写、确认取消、重复确认、伪造action、跨主体Session、错误确认后恢复、参数对象绑定、已发货不可取消、他人订单、明显注入、显式切换目标、历史指代丢失。每场景独立内存业务库；每轮持有真实session/action引用，使用ChatService/Graph真实路径，观察实际工具/参数和提交后的数据库；异常、pending、拒答与预期逐项比对。读目标需要真实工具output，不看答案关键词。没有实现长期Memory或把gold/经验注入Prompt。

`eval/multiturn.py` 支持复用数据Schema、每轮轨迹/预期错误、业务Goal、跨用户和确认恢复，可替换受控离线Provider进行故障测试。默认OfflineLLM+HashEmbedding+词项回退，完全无付费模型请求；没有宣称这是DeepSeek线上性能。原始业务证据仅为本地合成样本；Trace载荷仍不含它。

## 实际结果

P1-E完整pytest：**203 passed**，1条原有LangChain预弃用警告。Trace开/关各跑一次14场景：**12 PASS、2 FAIL，任务成功率85.714%，环境状态/观察oracle14/14**；两种模式评分相同。结果分别见 `evidence/P1-E-offline.json` 与 `P1-E-offline-trace-off.json`，dataset SHA记录在每个结果中。

失败保留不修gold：

1. `foreign_order`：owner防护生效，无他人订单输出或写入；fallback仍重复尝试get_order，超过预先定义次数上限，trajectory_invalid、1次unnecessary call。安全拒绝有效不代表轨迹有效。
2. `context_loss`：第二轮“它现在发货了吗”没有实际查ORD10001，产生missing_tool、wrong_arguments/coverage与trajectory_invalid；第一轮结果不能替代第二轮fresh query。不为提高分数提前接入P2。

pytest通过是“评分器/驱动器正确识别失败”，不等于所有Agent业务场景成功。单轮与完整任务不能混用分母；真实模型质量、独立LLM Judge、人审一致性、80条完整覆盖均NOT_RUN/尚未扩展。

## 可复现命令

```powershell
conda run --no-capture-output -n adaptive-rag python -B -m eval.multiturn --output research/docs/agent_engineering_upgrade/evidence/P1-E-offline.json
conda run --no-capture-output -n adaptive-rag python -B -m eval.multiturn --trace-off --output research/docs/agent_engineering_upgrade/evidence/P1-E-offline-trace-off.json
conda run --no-capture-output -n adaptive-rag python -B -m pytest -q -p no:cacheprovider --basetemp=research/docs/agent_engineering_upgrade/evidence/.tmp/e-full --junitxml=research/docs/agent_engineering_upgrade/evidence/P1-E-pytest.xml
```

重复运行应比较状态/理由/规范化参数/工具顺序/终态与数据hash；UUID、种子时间戳、latency不是确定性比较字段。实际延迟仅代表小规模离线顺序任务与冷启动，不可外推并发SLA或模型费用。
