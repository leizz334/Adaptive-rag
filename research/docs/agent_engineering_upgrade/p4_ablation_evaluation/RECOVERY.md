# P4-D 恢复检查点

阶段实验已结束；不自动进入P4-E，不再发模型请求。Experience Active保持关闭。

- 分支 `codex/p4-ablation-evaluation`；基线 `75689d2276c19c51354a0d27966597a23c9063d4`。
- D0 `1a5e8b1aa21a9b7e2df3684481100b81ceb75c66`；D1 `f4ba8b5f4219732959b95d5262fe2953bbb1ba31`。
- D2 `bd3b2ab691f88abec43de10b77609e98c220fe3d`；D3 `626422f6813d31cfa006ef2781ff48a319388e13`。D4实际提交查git log与delivery.json。
- 架构决策原文在PLAN.md；禁止重初始化或新Worktree；复用Ubuntu .venv与既有Compose。
- 全局账本 `runs/ubuntu_D_20261111_01/requests.json`：79 RESPONSE、45050 Token、上界US$0.0178215，0未知/重试；已消费标记与原始请求保留。禁止重放baseline、development或independent_test，不能重置ledger。
- D0 freeze单独保留；成功配对固定freeze_d2_v2.json，173文件hash与7个依赖版本通过核验。首个freeze_d2.json在配对前启动失败，保留历史，不据它重跑。
- 完整开发检查点后才执行独立阶段：development_02、independent_test_01。首development worker启动失败exit3；其API清理exit0；各记录分开解释。
- pytest 858PASS/1历史SKIP，Ruff348文件/Mypy150源文件/pip PASS；冻结历史214案例新增PASS→FAIL为0。已通过的付费实验与全量验证不重跑。
- D所属与B回归所属共6容器已停止，卷保留；私有CPU模型及manifest保留。原有MySQL运行。不要prune/down-v或覆盖.env。
- 模型revision/文件SHA在evidence/model_download.json；权重不入Git；其他机器需按固定revision重新获取并校验，不能替换成Hash或Lexical冒充。
- 完整开放语义NOT_ASSESSED；14臂审核packet/template及D0独立packet均无伪造人工标签。当前源版本无合格经验，E0/E2 NOT_RUN。
- 结论PARTIAL_PASS：受限Memory收益；总体收益未建立，RAG下游收益未建立，Experience收益未建立。

## 交付恢复

先读AGENTS.md、feature-list.json、progress.txt、Git与delivery.json，核对已存在证据。若只剩交付，正常push本分支，使用git ls-remote精确比较HEAD；严禁force-push。最终metadata提交自身hash由Git/final response给出，delivery.json记录此前已验证检查点，避免递归改写。完成后STOP。
