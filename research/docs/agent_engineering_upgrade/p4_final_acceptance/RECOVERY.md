# P4-E 恢复检查点

本阶段复用现有Ubuntu目录/.venv/Compose，没有Worktree或重新Initializer。基线 `71b53b9ab042af75f3dfed1dc46d85a3e2228a27`；分支 `codex/p4-final-acceptance`。

恢复顺序：读AGENTS.md→feature-list.json→progress.txt→Git log/status→本目录证据。PLAN.md保存架构决策，旧P0–D Gold/报告/ledger不可修改。源码仅日志边界最小修复；其他新代码都是本阶段隔离runner与回归测试。

- E0 `29dbb1b`：工程审计、20条原始D交互审核包/空白人审CSV；不代填标签。
- E1 `ce96fa3`：53真实矩阵+7补充通过；日志RED3修复GREEN；私有KB租户隔离真实adapter RED仍FAIL，禁止该用途部署。
- E2实际提交见Git log：实际ASGI两次启动、48热+2首次受控请求性能及Ubuntu复现指南。
- E3实际提交/最终push核验见delivery.json、Git与最终答复。交付元数据的自身hash不递归写入文件。
- 全量/静态/legacy检查结果保存后不盲目重跑已通过任务。所有helper run ID以ubuntu_E1/E2/E3开头，旧结果不覆盖。
- 初次deployment停机判据错误：Uvicorn SIGTERM优雅退出-15，FIRST证据保留；修正为exit0/-15且shutdown complete日志存在，后续VERIFIED两轮通过。
- 本阶段付费0，外部网络与Key在测试wrapper/worker双重禁止；C/D ledger保持字节一致。禁止重新调用已完成的付费实验，不重置账本。
- 隔离manifest位于 `../p4_dependency_integration/.private/p4b_20261111_p4e_01/manifest.json`，只在本机私有；不要输出其凭据或提交Git。
- demo凭据在同目录p4e_api.private.json，有效1天，生产凭据不能沿用。新机器按DEPLOYMENT_GUIDE另选唯一项目名。
- owned三依赖停止后保留卷；不要prune/down-v/批量kill或操作其他资源。实际清理结果见evidence/e3_cleanup.json；已有MySQL应持续运行。
- 确认后写入如遇不确定响应，应查询现有幂等/业务状态；不得创建新action或绕过确认盲目重放。当前“进程异常/取消后SQL回滚”不是机器断电RPO/RTO保证。

交付只允许正常push本分支并git ls-remote核验HEAD；禁止force。完整语义NOT_ASSESSED；生产私有KB隔离FAIL，Redis故障strict throttling未满足，外围生产条件未验证。工程材料可交付，不强称生产安全全过。完成后STOP，不自动启动其他研究/开发阶段，Experience Active始终NO。
