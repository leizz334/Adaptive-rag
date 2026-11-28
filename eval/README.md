# 评测复现

当前主分支的四路检索和真实生成复测见 [RAG 专项复测](rag_refresh/README.md)，包含模型修订、逐题结果和无需密钥的复算命令。

评测使用合成订单、商品、对话和仓库内的政策资料。命令从仓库根目录执行。使用项目已有的 Python 3.11 环境，或运行 `uv sync --locked --extra dev` 后，用 `uv run python` 执行以下命令。

## 离线验算记录

```bash
python -m eval.reproduce agent --verify
python -m eval.reproduce skills --verify
python -m eval.reproduce memory --verify
python -m eval.reproduce rag --verify
```

这四条命令通过仓库中的冻结样本、逐例记录和汇总验算，无需模型密钥或历史 Git 对象。公开包中保留了原始评分逻辑和合成样本。Agent 和 Memory 验算还核对输入指纹、实际工具轨迹、服务端用量和历史费率。RAG 验算从 Gold 标注和检索记录重算排名、上下文覆盖和关键词命中，再汇总已记录的裁判判决。

| 评测 | 已记录结果 | 证据 |
| --- | --- | --- |
| 完整 Agent | 15 个真实 DeepSeek 配对。P0 到最终源码严格通过由 6/15 提升到 12/15，实际工具证据字段由 8/26 提升到 20/26。主批总计 160 次 HTTP 与 35 个完整执行样本，另含专项对照。 | [主批汇总](release/evidence/agent/main/summary.json) |
| 有限 ReAct | 开启组 4 例、32 次 HTTP，均未到达可补查的入口。关闭组只完成 1 个专项用例，无法形成完整配对。默认关闭。 | [补充汇总](release/evidence/agent/react/summary.json) |
| Agent Skills | 三个独立的 Intent 内容长度对照中，目录提示共 4,381 个输入 Token，预载全部指令共 7,579 个，目录提示减少 42.2%。 | [配对记录](release/evidence/skills/preload.jsonl) · [六次请求回执](release/evidence/skills/requests.json) |
| Memory 和上下文 | 七个真实配对中严格通过由 1/7 提升到 5/7，证据字段由 4/17 提升到 14/17。相同七例中，旧版主批用量为 20,713 Token，最终源码复测为 19,259，合计减少 7.0%。 | [配对汇总](release/evidence/memory/main/summary.json) · [最终复测](release/evidence/memory/retest/summary.json) |
| RAG | 自然停止的五组各 65 例，每组 Recall@3 为 94.62%、Hit@3 为 62/65，325 次均无全局重排。固定两轮的五组各 5 例，15 次实际全局重排未改善排名、证据覆盖或回答正确率，开关保持关闭。 | [自然停止默认组](release/evidence/rag/natural/A-summary.json) · [两轮重排组](release/evidence/rag/forced/B-summary.json) |

完整 Agent 冻结集包含 123 个用例及 166 轮。19 个不同用例进入真实 API 执行，104 个用例的真实模型状态为 `NOT_RUN`。严格通过同时核对要求的工具及参数、实际业务证据、关键回答事实和状态变化。RAG 正确率和忠实度来自模型裁判，分母随有效判决数变化。Skill 指标取自只改变指令加载方式的三对实际 Intent 调用。

独立的工程证据记录了 PostgreSQL 16.15 的四项真实数据库测试以及 FastAPI 真实 HTTP 和 SSE 检查。 [数据库证据](release/evidence/engineering/postgres_final.json) · [HTTP 和 SSE 证据](release/evidence/engineering/http_final.json)

## 运行本地 Agent

```bash
python -m eval.reproduce agent --arm E --offline --dry-run --output data/local/release-offline
python -m eval.reproduce agent --arm E --offline --output data/local/release-offline
```

离线运行阻断 HTTP，覆盖全部 123 个用例，生成逐例轨迹和 `offline_E_summary.json`。模型评测状态为 `NOT_RUN`。本次用公开发布源码执行，完成 123/123，严格通过 52/123。

## 发起新的真实评测

真实 Agent 运行使用环境变量 `DEEPSEEK_API_KEY`。从干净的发布提交运行 E。先用 `--dry-run` 核对源码、冻结样本和用例安排。去掉该参数后会发起付费请求。每批各组使用同一输出目录和共享账本。

```bash
python -m eval.reproduce agent --arm E --dry-run --output data/local/release-live
python -m eval.reproduce agent --arm E --output data/local/release-live
python -m eval.reproduce agent --collect --output data/local/release-live
python -m eval.reproduce agent --verify --output data/local/release-live
```

历史 A 可从公开的 `codex/memory-v2-p0` 分支另行检出完整提交 `38c4e2071cb9f9c8fc04ee9f834fe2635b88aea9`。在该检出目录中运行以下命令。将两个路径替换为发布仓库下的脚本绝对路径和与 E 共用的输出目录。已有主批 E 来自当时锁定的源码版本，新运行的 E 会记录当前发布提交。

```bash
python /path/to/release/eval/reproduce.py agent --arm A --dry-run --output /path/to/release/data/local/release-live
python /path/to/release/eval/reproduce.py agent --arm A --output /path/to/release/data/local/release-live
```

RAG 的新运行使用仓库内 65 条 Gold 标注、39 篇政策原文、真实 DeepSeek API、稠密向量及 Cross-Encoder。安装 `rerank` extra，并在配置中开启 `LOCAL_EMBEDDING_ENABLED`、`CROSS_ENCODER_ENABLED`，填入可用的真实模型凭据。默认运行五组，`--groups A` 可只运行默认组，`--force-two-hops` 可在五条跨文档题上重做两轮探测。每种设置使用独立输出目录。已记录的历史实验使用相同的 39 篇政策原文，当时的索引由开发阶段的分块配置生成，含 127 个 Chunk。

```bash
python -m eval.rerank_ablation --non-thinking --groups A --output data/local/rag-natural
python -m eval.rerank_ablation --non-thinking --force-two-hops --output data/local/rag-two-hop
```
