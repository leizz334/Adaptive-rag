# S1-Web 恢复

固定Ubuntu工作目录和`.venv`，分支codex/s1-web-upgrade，基线3fe745c2a77b28075ce77a1f0961381748c00928。先读AGENTS.md、上级feature-list.json/progress.txt、PLAN/AUDIT和git log/status，按实际证据继续，不重新初始化。

Web-0 cdc4b92：回答名称/定制/refund遗漏最小修复；Web-1 2133620：认证内存会话与HTTP/SSE；Web-2 fe456cb：知识库/HITL及共享受保护只读检查API；Web-3 c6ab8ac：执行UI；Web-4 ace0ddf：Experience历史面板。Web-5最终提交见delivery.json/Git。

不改历史Gold/原始付费实验/S1EX账本；旧EX frozen源码可从其Git提交还原，本Web源码有授权修改，不能声称当前文件仍满足旧sourcefreeze或重新批准经验。Experience当前版本未重新资格验证，面板只是历史快照，无Active。

本阶段真实模型付费请求/Token/费用均0。真实浏览器采用受控OfflineLLMProvider和本地真依赖。demo私有文件 `.private/demo_api.json` 含临时凭据，禁止提交/打印；服务端仍走原生产Authenticator/ACL/Redis原子限流/HITL/幂等。重启不自动重新seed取消状态或重放确认。

原始失败记录保留：Web0 RED、frontend缺模块/资格、authrace和协议RED、首轮浏览器selector/文案/状态码不符、重复合成语料/strict locator、首次fullsetup普通迁移后被fresh-roundtrip门禁拒绝。验证环境切换为全新空库走回环，不删除/重置原库。

Owned项目：p4b_20261112_s1web_01浏览器demo；s1web_verify_01保留首轮初始化状态；s1web_verify_02正式全量回归。结束以guarded sandbox stop全部保留卷，不操作既有MySQL；清理证据见evidence/cleanup.json。跨进程Trace查询可能404；未支持持久历史、组织共享、生产登录发证或PDF解析。

人工语义审核仍NOT_ASSESSED，真实Experience收益仍NOT_ESTABLISHED。正常Push/ls-remote核验后STOP，等待后续授权；不启动S2/S3/P5，ExperienceActive=NO。

本机 Node工具路径：`$HOME/.local/share/s1web-tools/node-v22.23.5-linux-x64/bin`，可临时加PATH；不修改HOME变量或系统安装。原S1-EX私有SQLite哈希仍与原freeze吻合，当前授权源码修改不代表旧经验重新兼容。
