# P4-F 恢复记录

基线 `a081291f9665f39fccb590600d51918773869906`，分支 `codex/p4-security-remediation`，复用Ubuntu固定目录/.venv/Compose，无Worktree/Initializer。先读AGENTS.md、feature-list/progress、Git状态与本目录证据。SECURITY_DESIGN.md保留架构决策和策略；不可改旧Gold/raw来通过测试。

- F1 `288b2d9c32f04a53e8aab3dd40869f85302eb403`：端到端private主体隔离；SQL迁移0004，租户generation锁、scoped BM25/Qdrant/缓存/重排/引用与文档生命周期；RED与16GREEN保留。
- F2 `d6090214a9daa6ff2cef6454442dfdc8ea802a1e`：原子Redis failclosed、超时503/耗尽429、恢复、全局多进程配额、远程Embedding启动保护；最终9GREEN及组合18GREEN保留。
- F3实际提交/Push远端核验见delivery.json、Git与最终答复。metadata自身hash不递归写入文件。
- 新F UUID run目录保存每条HTTP输入/输出、合成subject、配置与SQL中断快照；fixture token是公开测试常量，不得生产使用。私有manifest/日志/实际凭据/.env不提交。
- 仅新所属project `p4b_20261111_p4f_01`；私有manifest在B helper `.private/` 中。依赖最终停止但保留卷；不要prune/down-v，原有MySQL保持运行。若恢复服务，用sandbox up/start并核对owner/端口，不使用任意DSN。
- tests使用offline wrapper清空Key并禁止外网；实际ASGI子进程也包裹相同约束。C/D及其他历史计费ledger与原始实验不变；不重跑付费任务。
- 旧B3 Redis故障“200降级”测试已强化为503/noTools/noWrites；原始历史结果仍保留。显式ordinary-read utility的fail-open测试不代表敏感运行时策略。
- 发生不确定业务响应时先查业务/幂等状态，不创建新action自动重放。限流超时可保守占quota，但不会继续业务。索引在途取消导致可用性下降时等任务结束再显式重索引，SQL权威拒绝未知revision。
- 认证subject=namespace，非组织共享；事务快照授权不撤回先前历史/在途网络数据。孤儿清理/备份擦除、外围生产设施及完整语义未验收。

完成所有验证后只进行scoped commit、正常push和git ls-remote精确HEAD核验。最终工作区应干净，停止P4-F，不自动执行P5/其他研究开发，不启用Experience Active。
