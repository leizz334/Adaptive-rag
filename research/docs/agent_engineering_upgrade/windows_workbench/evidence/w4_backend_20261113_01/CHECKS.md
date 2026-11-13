# W4 backend results

Source checkpoint: `e67eb52dff19d5c47e166e22faba973020a1e038`.
All commands used the existing Linux development environment and the fresh
`p4b_ww_w4_20261113_01` owned dependency project. No paid requests or Experience
Active were enabled. Original raw command logs and JUnit remain under that
project's ignored `.private` directory.

| Check | Actual result |
| --- | --- |
| Full offline-wrapper pytest over `tests` and `research/docs/agent_engineering_upgrade` | **PASS: 1023 passed, 1 skipped, 1 warning, 419.89 seconds**; JUnit 1024 cases, 0 failures, 0 errors |
| Fresh historical regression | **PASS: 0 regressions**; 202/214 PASS, original 12 non-PASS retained |
| Ruff check over app/tests/eval/alembic/research/showcase | **PASS** |
| Global Ruff format check over those roots | **FAIL**: one unrelated, pre-existing, untracked preservation helper; 403 files already formatted |
| Format check excluding only that exact old untracked file | **PASS: 403 files already formatted** |
| Mypy | **PASS: no issues in 162 source files**; four notes about unchecked untyped bodies |
| pip check | **PASS: no broken requirements** |

The pytest skip is the frozen historical
`test_real_http_e2e[trusted_identity_authentication]` probe: its legacy client
`user_id` is deliberately not claimed as trusted authentication. The separate
production-verifier real TCP authentication matrix passed all 20 cases. The
actual owned dependency suite passed 13 PostgreSQL/Redis/Qdrant cases, and the
real dependency HTTP/SSE matrix passed 20 cases. The one warning is the installed
LangGraph dependency's `LangChainPendingDeprecationWarning`.

Fresh historical outputs are preserved at
`p4_dependency_integration/runs/ww_w4_20261113_01_legacy/`: 80/80, 13/16,
30/30, 33/33, 23/24, 22/30, and long-window 1/1. No old result was overwritten
or reclassified; the original baseline comparisons produced zero regressions.

The exact global format failure is
`research/docs/wsl_docker_engine_setup/verify-preservation.py`. Its SHA-256 is
`e8de7adc08ceef339b86ee9b900e4c65a5d9a303799c74e252121f76ced77a25`, matching
the original private preservation baseline byte-for-byte. The file was not
modified. The original failed format result remains in `checks.json` and
`ruff_format_result.json`; the helper's overall exit status was 1 because of
that failure. The additional scoped result is separate in
`scoped_format_result.json`. An initial scoped invocation using
`--extend-exclude` was rejected by this Ruff CLI; the supported `--exclude`
option produced the passing scoped result without changing files.

The post-run sandbox ownership/loopback check passed. After the parent's final
browser verification, the existing guarded helper stopped only this owned
project. Post-stop inspection confirmed all three containers are exited and all
three volumes remain, with owner/project labels matching the private manifest;
see `stop_verification.json`. PostgreSQL and Redis exited with code 0, Qdrant
with code 143 following the requested stop. The existing user showcase and W1
browser project were outside this runner's target scope and received no
lifecycle commands from it. The original failed format log remains preserved.
