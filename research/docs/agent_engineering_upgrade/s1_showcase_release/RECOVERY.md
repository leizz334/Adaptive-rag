# S1-Release 恢复检查点

基线66eeaa27ae85f0517470f8ef3405ade2c2da9a78，分支codex/s1-showcase-release；固定Ubuntu目录和`.venv`，无新Worktree。读AGENTS、上级feature-list/progress及Git实际状态，不重复初始化。

R1启动器检查点03cee60e6ef6428dc79a79fe2b4a490eff8bd9e0。主演示run `release_20261112_01`，owned项目`p4b_showcase_release_20261112_01`；私有配置在本目录`.private/<run>/`，Docker清单在既有P4-B `.private/<project>/manifest.json`。它们包含凭据，勿打印/提交。R1首次代理继承故障已保留，修复清理子进程代理，不改用户环境。

scripts.showcase init只用于全新run，拒绝现存目录；start/serve恢复现存资源，禁止重复迁移回环或重置取消状态。stop按PID启动时间/命令/cwd/UID和Docker标签核验，仅停止本run、保留卷，不操作MySQL/其他资源。临时凭据1天到期后不能无审批替换或覆盖原文件；使用全新run演示即可。

R2真实浏览器6PASS，无Mock无付费；ORD95102已取消、同Action重放审计1条；ORD95104撤销后仍paid。后续浏览器用尚未取消的ORD95103/95105/95106/95107，不复位历史。每轮私有原始报告唯一ID，公开汇总不含Token。

干净安装验证：Git archive R1源码到忽略的clean_install_01目录，独立venv/npm ci，不创建Git工作树或读取.env；主.venv不变。该验证是依赖安装/import/前端构建，不冒充另一套生产部署。版本及范围见r2_clean_install_VERIFIED.json。

R3文档和R4/R5状态以实际feature-list与progress为准；未完成检查不得标PASS。最终停止/Push/精确HEAD证据将在本报告和delivery.json落盘，禁止依据对话记忆重跑已完成付费或业务写操作。所有新增模型付费请求0，ExperienceActive关闭，不自动S2/S3/P5。

本机Node可临时设置`PATH="$HOME/.local/share/s1web-tools/node-v22.23.5-linux-x64/bin:$PATH"`。不要改写HOME变量、用户.env或旧阶段原始结果。
