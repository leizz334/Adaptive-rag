# S1-EX 恢复检查点

分支 `codex/s1-ex-experience-optimization`，基线 `b88b2cbe584d061418206c9301078ebbd7e8f08e`。

EX0 `8f4a5e8443b31fc20ca57f7f2d9fc99599ad515c`；EX1/付费冻结 `8615f9c8f8da4cf1b40ba6846b95d1a2ac7e0c4c`；开发审核 `8978c4eeaa0ea34795ca9a5813057712da0d2ad9`；EX2 `9a4101edffc08f059fece0d9f4ed3156fed1a0f7`。EX3 交付提交见 delivery.json 与真实 Git log。

先读 AGENTS.md、上级 feature-list.json/progress.txt、当前 Git log/status 和此报告，按实际证据恢复，不重复初始化。付费目录 runs/ubuntu_EX_20261112_01 已有4个 TRIPLET_COMPLETE、12个 STARTED；60个 RESPONSE、54,845 Token、US$0.0214854上界，未知/重试0。停止新增模型调用，不自动重新运行 paid worker/run。

冻结源码/Gold/评分器/模型配置/依赖/许可/只读数据库未改变。原 `.private/experience.sqlite3` 是付费 freeze 的私有输入，禁止覆盖；完整 freeze/分析需保留此原件。公开 demo 重建新库，仅离线记录响应重放，不保证数据库字节等同。新观察失败提案在另一私有 SQLite，公开导出 NEEDS_REVIEW/UNREVIEWED，不能自动授予 E2 资格。

全量测试/历史回归已完成，详见 evidence/ex3_checks.json；无源码变更不要重跑已通过实验。仅文档或交付元数据更新不需要新增付费测试。隔离项目 p4b_20261112_s1ex_01 和 p4b_20261112_s1ex_verify_01 结束时使用原 guarded sandbox 停止，数据卷保留；未操作既有 MySQL，详见 evidence/ex3_cleanup.json。私有 manifests/凭据不得提交。

所有实际语义人工字段仍未填写；不将AI标签变成人工审核。现有回答 coverage/fallback 丢字段问题及有界评分假阴性保留风险，不事后修 Gold 或凑正收益。

正常 push，无 force；最终 git ls-remote 与本地 HEAD 精确匹配，状态记录在 delivery.json（记录可验证的前一交付提交以避免自引用），最终 Git HEAD 由终端再次核验。

NEXT_ACTION=STOP，等待用户后续 S1 项目产品化授权。Experience生产Active=NO，P5_STARTED=NO。
