# W4 isolated backend verification preparation

Prepared on 2026-11-13 in the existing `p3-experience-validation` worktree.
No product source, repository metadata, existing dependency stack, or `.env` was changed.

- Fresh owned project: `p4b_ww_w4_20261113_01`.
- PostgreSQL, Redis, and Qdrant started using the existing guarded sandbox commands.
- Initial empty PostgreSQL database completed upgrade → base → head; the checked
  `migration_roundtrip.json` marker prevents a later fixture from repeating that reset.
- The sandbox's owner, volume, and loopback endpoint checks passed after preparation.
- Existing Linux environment reused: `/home/panda/.venvs/adaptive-rag-workbench`.
- Helper Ruff check and format check passed.
- Final full pytest, historical 214 cases, and project static checks have **not run**
  at this preparation checkpoint; they wait for W3 completion.

Native Linux Git cannot interpret the existing Windows `D:/...` worktree gitfile
and common-directory pointers. The runner supplies `GIT_DIR`, `GIT_COMMON_DIR`,
`GIT_WORK_TREE`, and the parent's audited `GIT_OBJECT_DIRECTORY` only to its
process environment. This preserves the Windows metadata and bypasses the
previously diagnosed damaged loose-object directories. Read-only `rev-parse
--verify HEAD` succeeded at `315075ab85b0b0def72e2179fa6c09bae0aaf0f9`.

From the existing worktree, after W3 is ready:

```powershell
wsl -d Ubuntu-24.04 -u root -- /home/panda/.venvs/adaptive-rag-workbench/bin/python -m research.docs.agent_engineering_upgrade.windows_workbench.w4_backend_20261113 run
```

The helper sets `P4B_RUN_LIVE=1`, the private manifest path, and fresh explicit
HTTP/auth/API/legacy run IDs. It uses the existing offline wrapper to clear paid
keys and prohibit external sockets for pytest and the historical regression.
Raw command output and JUnit remain in the designated ignored `.private`
directory; public result JSON contains only commands, return codes, and counts.
Generated historical and HTTP evidence uses new run directories.

After the final checks, stop only this owned dependency project while retaining
all volumes:

```powershell
wsl -d Ubuntu-24.04 -u root -- /home/panda/.venvs/adaptive-rag-workbench/bin/python -m research.docs.agent_engineering_upgrade.windows_workbench.w4_backend_20261113 stop
```
