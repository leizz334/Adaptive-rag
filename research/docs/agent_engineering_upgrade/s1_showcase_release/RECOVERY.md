# S1-Release 恢复检查点

基线66eeaa27ae85f0517470f8ef3405ade2c2da9a78，分支codex/s1-showcase-release；固定Ubuntu目录和`.venv`，无新Worktree。读AGENTS、上级feature-list/progress及Git实际状态，不重复初始化。

R1启动器检查点03cee60e6ef6428dc79a79fe2b4a490eff8bd9e0。主演示run `release_20261112_01`，owned项目`p4b_showcase_release_20261112_01`；私有配置在本目录`.private/<run>/`，Docker清单在既有P4-B `.private/<project>/manifest.json`。它们包含凭据，勿打印/提交。R1首次代理继承故障已保留，修复清理子进程代理，不改用户环境。

scripts.showcase init只用于全新run，拒绝现存目录；start/serve恢复现存资源，禁止重复迁移回环或重置取消状态。stop按PID启动时间/命令/cwd/UID和Docker标签核验，仅停止本run、保留卷，不操作MySQL/其他资源。临时凭据1天到期后不能无审批替换或覆盖原文件；使用全新run演示即可。

R2真实浏览器6PASS，无Mock无付费；ORD95102已取消、同Action重放审计1条；ORD95104撤销后仍paid。后续浏览器用尚未取消的ORD95103/95105/95106/95107，不复位历史。每轮私有原始报告唯一ID，公开汇总不含Token。

干净安装验证：Git archive R1源码到忽略的clean_install_01目录，独立venv/npm ci，不创建Git工作树或读取.env；主.venv不变。该验证是依赖安装/import/前端构建，不冒充另一套生产部署。版本及范围见r2_clean_install_VERIFIED.json。

R3文档和R4/R5状态以实际feature-list与progress为准；未完成检查不得标PASS。最终停止/Push/精确HEAD证据将在本报告和delivery.json落盘，禁止依据对话记忆重跑已完成付费或业务写操作。所有新增模型付费请求0，ExperienceActive关闭，不自动S2/S3/P5。

本机Node可临时设置`PATH="$HOME/.local/share/s1web-tools/node-v22.23.5-linux-x64/bin:$PATH"`。不要改写HOME变量、用户.env或旧阶段原始结果。

## 最终验证恢复

R5全量951PASS0FAIL1历史SKIP/22前端PASS/typecheckbuildPASS/7真实ChromiumPASS/Ruff390/Mypy157/pipPASS；214历史案例202PASS12既有非PASS、0新增严格回归。R5取消使用ORD95103，审计1条；R2的ORD95102也仅1条，均不得重置重跑。

Git所有可达引用6459blob凭据检查通过；首次候选35个全部为无认证的合成SQLite路径，分类证据保留。旧Gold/raw/账本/经验数据保留。所属两个run最终guarded stop，6卷保留，MySQL仍运行，详见r5_cleanup.json。

会话刷新后重新认证，从Owner只读SQL接口取50会话/每会话100条user/assistant文本，过多截断；不恢复旧Trace/citation/提案，删除仅本页隐藏。迟到初始列表占位重复已修复，快速选择/身份变更的实际取消已验证。凭据24小时到期使用新run，不覆盖旧凭据。

下一步仅完成已授权正常Push/精确远程HEAD与交付元数据，然后STOP；已完成后按delivery.json/Git核对，不重新跑已通过/非幂等演示。S2/S3/P5未启动，生产ExperienceActive始终NO。
