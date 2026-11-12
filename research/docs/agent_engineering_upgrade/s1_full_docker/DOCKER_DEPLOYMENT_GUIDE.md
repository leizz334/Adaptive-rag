# S1-Docker 本地部署与恢复

此文描述独立的`compose.showcase.yml`路径。Ubuntu已完成真实容器、7项浏览器与重启持久化验收；Windows Docker Desktop为`NOT_RUN`。干净Git源码构建使用已验证Docker热缓存，单独冷下载尝试中断，未宣称冷缓存安装通过。原宿主`python -m scripts.showcase`路径及其私有状态继续独立使用。

这是受控业务演示：OfflineLLMProvider、Hash Embedding、lexical重排、M2；付费模型请求0，Experience Active为NO。工程运行结果不能代替真实模型语义质量或Experience收益评测。

## 启动

在包含本文件对应代码及`compose.showcase.yml`的仓库根目录执行。宿主需要可用的Docker Engine和Compose插件；无需安装Python、Conda或Node。首次镜像拉取与构建需要网络，运行时模型请求保持离线。

```bash
docker compose -f compose.showcase.yml up -d --build
docker compose -f compose.showcase.yml ps -a
```

等待`bootstrap`、`initialize`以退出码0完成，PostgreSQL、Redis、Qdrant及API健康。`up -d`返回本身不代表API已健康。API健康检查同时检查实际数据库、Redis、向量库、离线能力与Bearer认证。

打开`http://127.0.0.1:8000`。若8000已被宿主演示占用，在启动前选择其他端口，并在后续操作中保持相同项目与配置：

```bash
SHOWCASE_PORT=18000 docker compose -f compose.showcase.yml up -d --build
```

此时访问`http://127.0.0.1:18000`。不要修改或覆盖已有`.env`；本路径不继承宿主付费模型凭据。Compose仍可能读取常规项目配置，因此显式的`SHOWCASE_PORT`和项目名称应保持可追踪。

## 显式读取本机开发凭证

初始化在私有命名卷中随机生成A/B主体Token及哈希注册表。Token文件为UID1000所有、`0600`，父目录`0700`，API只读挂载；数据库密码使用另一个卷。启动日志不输出Token。

先检查凭证有效性并获取容器内路径，此命令只输出路径：

```bash
docker compose -f compose.showcase.yml exec -T api python -m app.demo.docker credentials
```

仅在私密本机终端，由本机操作者显式读取A主体Token：

```bash
docker compose -f compose.showcase.yml exec -T api python -c 'from app.demo.docker import read_credentials; print(read_credentials()["tokens"]["a"])'
```

将输出粘贴到页面“本地开发凭证”框。将命令中的`"a"`改为`"b"`可读取另一合成主体。此命令有意向当前终端输出秘密，请勿录屏、重定向到公开日志或提交输出；Token不要放入URL、VITE变量或共享报告。页面刷新后重新认证。

Docker凭证从生成起有效30天。到期、损坏或密码卷缺失等不一致状态会安全拒绝使用，重复启动不静默替换凭证。本文未提供原项目原地轮换流程；需要继续演示时，选择新的独立项目，保留原卷待检查：

```bash
docker compose -p adaptive-rag-showcase-next -f compose.showcase.yml up -d --build
```

新项目需避开已有Web端口。使用`-p`后，所有状态、取凭证与停止命令均须继续带相同`-p`，避免操作另一项目。新的项目会创建新卷与新合成数据，不恢复原项目业务历史。

## 状态、诊断与停止恢复

```bash
docker compose -f compose.showcase.yml ps -a
docker compose -f compose.showcase.yml logs --tail 100 bootstrap initialize api
docker compose -f compose.showcase.yml exec -T api python -m app.demo.docker health
```

最后一条成功时退出码为0且无输出。依赖失败可检查对应服务日志；不要仅凭API存活接口200判断业务就绪。分享日志前检查是否包含业务或私有内容。

停止与恢复保留现有容器和命名卷：

```bash
docker compose -f compose.showcase.yml stop
docker compose -f compose.showcase.yml start
docker compose -f compose.showcase.yml ps -a
```

恢复后等待API健康。也可使用同一项目的`up -d --build`重新协调服务；初始化保留有效凭证、匹配的合成记录和已取消订单，冲突时失败而非重置。不要通过删除卷来“修复”初始化错误，应先保留现场与诊断。

仅重启API：

```bash
docker compose -f compose.showcase.yml restart api
```

运行时网络允许列表在API启动时解析服务地址。若独立重建依赖导致其IP变化，待依赖健康后重启API，使其重新解析地址；普通容器restart与重新创建容器不同。

本文不执行自动清理。不要执行`down -v`、volume prune或删除命名卷；这些动作可能永久删除订单、会话、私有知识、Token和数据库密码。停止容器即可保留演示现场。

## 边界

只有API的Web端口发布到宿主`127.0.0.1`；PG/Redis/Qdrant没有宿主端口，使用内部网络服务DNS。API以UID1000、只读根文件系统、移除capabilities运行；一次性bootstrap具有创建文件和设置属主所需权限。依赖与初始化服务仅加入内部网络；API额外加入Web网络用于发布本机端口，API的外连限制由应用socket允许列表执行。不能将API的Web网络声称为网络层出站隔离。付费模型、云Trace与MCP关闭。

这不是对本机Docker管理员的保密边界。能够管理Docker的用户可以读取卷或容器内秘密；仅在可信本机使用，不暴露Docker socket或将页面公开转发。Compose项目与命名卷独立于宿主启动器；不要把原启动器的`.private`或凭证文件挂入此项目。Dockerfile仅复制指定应用/前端/迁移及公共知识素材，构建忽略规则排除嵌套`.env*`、`.private`与开发环境目录。

实测源码`fb6a1c3480a45e114badf5624c32ab59e0713d63`，Ubuntu隔离项目、真实Chromium/SQL与重启对照见[最终报告](S1_DOCKER_FINAL_REPORT.md)和`evidence/d3_real_01/acceptance.json`。宿主Python/Node仅用于开发验收脚本，部署运行不需要它们。

## 本机 Docker Snap 兼容限制

本次安装的Docker29.8 Snap/Ubuntu Core24中，开启`no-new-privileges`会使官方Python镜像在执行解释器前返回EPERM；真实RED矩阵见`evidence/d2_bootstrap_exec_RED.json`。Compose因此未启用该可选加固项，仍使用默认AppArmor/seccomp、非root API、只读根文件系统与capability限制。这些控制不等同于NNP，不能据此宣称生产安全加固完备。无需更改宿主Docker配置。

API单独增加Web桥接网络后发布loopback端口；PG/Redis/Qdrant不加入该网络。相关行为与边界参见[Docker Compose网络说明](https://docs.docker.com/compose/how-tos/networking/)。
