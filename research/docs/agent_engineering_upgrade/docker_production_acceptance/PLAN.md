# Docker 正式环境升级与验收 Implementation Plan

**Goal:** 将现有正式工作台 8000 升级到已验证修复版，保护所有旧数据，区分 Offline 实测与未授权的真实付费测试。

**Architecture:** 复用既有工作树、Compose 和 LangGraph 架构。仅替换正式 API；不重跑 bootstrap/initialize、不重建数据库。先保存镜像和配置，再验证持久数据与功能，最后按归属清理旧测试容器。

**Tech Stack:** WSL2 Docker Engine/Compose、React、FastAPI、PostgreSQL、Redis、Qdrant、Chromium。

**Spec:** 用户本轮 W1–W5 指令。

## Global Constraints

- 不创建 Worktree，不覆盖 .env，不改变历史证据；保留 be2931f 和 287a886。
- Git 仅使用已校验的进程级对象缓存，不操作损坏 loose objects。
- 不调用付费模型；无明确预算授权时标记 REAL_LLM_NOT_RUN。
- 保留全部数据卷，禁止 prune/down -v；不影响其他任务。
- Experience Active=OFF；所有原安全门禁保持。

## Review Focus

- 升级仅替换 API，防止依赖与初始化服务被意外重建。
- 迁移版本必须兼容，禁止覆盖旧订单、私有知识库、Memory 与凭证。
- 测试写操作仅使用确定的合成订单和本轮隔离政策。
- 浏览器证据不输出凭证，真实与 Mock 验收明确分开。
- 清理前核对容器归属、活动任务、连接及数据卷保留情况。

## Tasks

- [x] W1：只读基线、数据指纹、配置及回滚镜像记录，核对版本，任务独立提交。
- [x] W2：构建最新镜像；Compose up --no-deps 仅替换 API；健康和数据指纹验证，失败回滚。
- [x] W3：8000 实际 HTTP/SSE 与 Chromium，订单/Memory/RAG/HITL/Owner/异常/Trace 验证。
- [x] W4：现有 Real Dev 与预算 MockTransport 回归、前后端测试；真实付费标记未运行。
- [x] W5：确认无其他使用者后清理 18083 测试容器，P4B 保持停止，保留全部卷；中文报告、普通 Push、精确 HEAD 核验。

按用户已明确授权的顺序直接执行；无产品代码变更则不新增镜像实现测试。
