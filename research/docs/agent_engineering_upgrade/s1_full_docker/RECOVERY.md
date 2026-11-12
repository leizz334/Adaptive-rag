# S1-Docker recovery

Authorized base `3ba2271d0ce8a70bd2de07278ae274bb782d6659`, branch `codex/s1-full-docker`, fixed Ubuntu checkout, existing `.venv`; no Worktree or repeated Initializer. Read AGENTS.md, parent feature-list.json/progress.txt, actual Git status/log and evidence before resuming.

D1 checkpoint `3d8c47a`: real multi-stage Node24/Python3.12 runtime image build, UID1000/read-only/network-none smoke, frontend assets/Alembic0004/no dotenv/credentials/research. First PyPI download timeout retained as RED; same build succeeded on retry. Official base image archives and Buildx/crane downloads checksum verified, private cache retained; no daemon/system changes.

D2 one-command deployment is in progress. Its explicit owned project is `adg_s1docker_20261112_01`; private target/port in `.private/d2_project.json`, build/start log `.private/d2_first_up.log`. Do not repeat initial bootstrap against unrelated resources or remove any volumes. Current task statuses remain false until actual acceptance. Runtime secrets only in per-project named volumes, never copy into reports/Git. Credentials expire after30days and are not silently rotated.

Regression evidence already complete: `evidence/d4_full_VERIFIED.xml` has964PASS/1historicalSKIP; frontend22PASS/typecheck/build; Ruff/Mypy160/pip PASS; legacy214 has202PASS12oldnonpass and0new strict regressions. These tests used the separate guarded host run `docker_verify_01`, project `p4b_showcase_docker_verify_01`; host startup/health/Bearer/offline checked and stop retained3volumes. Do not rerun verified experiments unless implementation changes justify regression.

Next: finish D2 real healthy initialization/auth/data/log checks and task-scoped checkpoint. Then Git archive that committed source into a new ignored directory (not a Worktree), build/start another fresh checked Compose project and run `verify.py` real Chromium/PG/knowledge/history/restart/stop-start persistence checks. Preserve intermediate failure evidence and use unused cancellation fixtures; never reset already-cancelled orders or old experiment data. Record source/image hashes and exact project before every lifecycle action. D4/D5 checkpoint only after their dependencies and criteria pass.

Final: update documentation/results, preservation and actual-secret scan, stop only verified owned services and retain volumes, normal Push and `git ls-remote` exact HEAD, then STOP. Windows NOT_RUN; paid requests0; Experience Active NO; no other phase authorized.

## D2 completed / D3 running

D2 checkpoint `fb6a1c3480a45e114badf5624c32ab59e0713d63`: actualone-command startup,2one-shotexit0/4healthy,PG0004/8orders+items,twoowners,modes/logscan and2concurrentinitializers unchanged;14unitPASS. Two real REDs preserved: DockerSnap NNP prevents exec (optional flag omitted; default AppArmor/seccomp retained); internal-only API got no published endpoint (only API also joins webbridge; app socket allowlist still restricts egress, no network-level API egress guarantee). Do not claim NNP or production-hardening acceptance.

D3 clean source `fb6a1c3` Git archive: `.private/clean_source_fb6a1c3_01/`, project `adg_s1docker_20261112_02`, loopback35691, config `.private/d3_project.json`, real build/start `.private/d3_clean_up.log`. Clean file modes cause a fresh rebuild rather than host-tree layer reuse; source has no.env/.git/hostruntimes. Run current `verify.py` against this exact source/project/port with NEW `--output evidence/d3_real_01` once startup completes. Existing root frontend test runner uses Node22 local path; image uses Node24 build. Never repeat browser business after success; recover from intermediate evidence on failure.

Final full pytest runs with distinct IDs `ubuntu_DOCKER4_final_*_20261112`, same guarded host dependency manifest; output `evidence/d4_final_full_VERIFIED.xml` and private `d4_final_pytest.log`. First full964PASS evidence remains; added network contract test requires final965full. Ruff396files currentlyPASS; Mypy160/pip/frontend22/legacy214 previouslyPASS. Stop owned hostdeps again after final test. MySQL remains unrelated/running.

## 工程验收已完成

D3检查点`fbf6cdfcc6d2a2c6716543328a2977ec3deb07b3`；D4检查点`3eb22a5`。真实Chromium7PASS，三个恢复阶段凭证/SQL/KB/historyOwner隔离不变。ORD95102已取消/审计1，ORD95104撤销后paid，禁止重置并重跑已完成浏览器业务。最终965PASS/1历史SKIP；前端22、类型构建、Ruff396、Mypy160、214历史0新增严格回归通过。

冷下载中断证据`d3_clean_download_INTERRUPTED.json`；最终是源码字节不变、权限统一后的正常Docker热缓存构建，219镜像文件匹配归档，不声称冷缓存安装PASS。全栈恢复后直接Qdrant持久点与Redis AOF验证完成。

所属两套Compose及host回归服务均已停止；13卷保留、MySQL仍运行。不要再启动或重新执行已通过业务；下一步仅D5文档/源文件最终检查点、正常Push、精确远程HEAD、交付元数据后再次正常Push/HEAD，然后STOP。Git身份用单条命令`git -c user.name=Codex -c user.email=codex@openai.com commit ...`沿用历史，不改全局配置。

## 交付完成

D5源码检查点`ca5feb323c30fb02582b885333166a8be7241441`已正常Push，git ls-remote精确一致；D1—D5均passesTrue。交付元数据随后正常Push，最终HEAD以Git/最终答复为准，不递归写自hash。全部授权工作完成，NEXT_ACTION=STOP，不重跑已通过实验、不启动其他阶段，Experience Active=NO。
