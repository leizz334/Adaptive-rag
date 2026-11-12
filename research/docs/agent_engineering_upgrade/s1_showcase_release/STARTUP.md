# 已验证的 Ubuntu 启动路径

前置：Python3.11+虚拟环境、Node20.19+或22.12+、Docker Engine及Compose。复用已有`.venv`，不覆盖`.env`。新克隆可执行`python3 -m venv .venv`和`.venv/bin/python -m pip install -e '.[dev]'`；后续隔离安装证据见最终报告。

```bash
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m scripts.showcase init --run-id my_interview_01
.venv/bin/python -m scripts.showcase serve --run-id my_interview_01
```

init必须选择未使用run-id，只含小写字母/数字/下划线、最长24字符。它复用原有guardedCompose，创建全新PG/Redis/Qdrant、空库迁移回环及合成数据；随机开发凭证写入忽略的0600私有文件。serve前台运行FastAPI并提供已构建React页面，阻止外部推理网络、清除本子进程代理、保持生产认证/私有ACL/Redis全局限流/HITL/幂等；不是生产登录/发证系统。

另一终端执行：

```bash
.venv/bin/python -m scripts.showcase info --run-id my_interview_01
.venv/bin/python -m scripts.showcase status --run-id my_interview_01
.venv/bin/python -m scripts.showcase stop --run-id my_interview_01
```

info只输出本机URL及私有凭证文件路径；请在本机私下读取tokens.a或tokens.b并输入浏览器开发凭证框，不粘贴进聊天/日志/Git。status同时核查实际PG/Redis/Qdrant与Bearer主体，不把仅health200当完整就绪。

stop严格核对本run的进程启动时间、命令、cwd/UID及Docker标签，先停止自己的API，再停止3个服务，**保留所有卷**。不执行down -v、prune或kill任意端口。恢复同一运行用start后serve，不重复init或破坏性迁移。

```bash
.venv/bin/python -m scripts.showcase start --run-id my_interview_01
.venv/bin/python -m scripts.showcase serve --run-id my_interview_01
```

旧根目录docker-compose.yml只保留API镜像示例，未配置认证/外部依赖时应拒绝启动；它不是本阶段完整演示路径。`.env.example`是安全默认的参考，不能单独替代依赖/凭证初始化。Dockerfile镜像本阶段不冒充已经过生产部署验收。

开发凭证有效期24小时。start/serve恢复资源但不会替换过期凭证；到期后使用新run，不覆盖旧凭据或重置业务数据库。init中途失败的私有检查点也保留，先核对/停止本run已创建资源，再另选run-id，不删除原始证据。
