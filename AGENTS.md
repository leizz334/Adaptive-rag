# Adaptive-RAG — Agent Instructions
## 1. Project Information
- Project: Adaptive-RAG
- Repository: https://github.com/leizz334/Adaptive-rag
- Python Environment: Conda `adaptive-rag`


## 2. Long-Running Task Protocol

For multi-session tasks, use two logical roles: **Initializer Agent** and **Coding Agent**.

### Initializer Agent

Run only once per long-running project.

- Inspect the repository and existing Git state.
- Break the authorized scope into small, independently verifiable tasks.
- Create `feature-list.json`, `init.sh`, and `progress.txt` in the designated project state directory.
- Give each task a stable ID, acceptance criteria, dependencies, status, and a `passes` field initialized to `false`.
- Create an initial Git checkpoint commit containing only the authorized initialization artifacts, when safe.
- Never overwrite existing work, reset Git history, or commit unrelated changes.
- Record the initial Git commit hash in `progress.txt`.
- Do not repeat initialization in later sessions.

### Coding Agent

Run in subsequent sessions.

At the beginning of every session:

1. Read `AGENTS.md`, `feature-list.json`, and `progress.txt`.
2. Inspect `git status` and `git log`.
3. Reconcile recorded progress with actual files, commits, and test evidence.
4. Select one authorized, dependency-ready atomic task with `passes: false`.
5. Complete that task without mixing work from another task into its checkpoint.
6. Run its required validation.
7. Set `passes: true` only when all acceptance criteria are verified.
8. Update `feature-list.json` and `progress.txt`.
9. Commit only the task-related changes when safe and authorized.
10. Record the real commit hash, then automatically select the next authorized,
    dependency-ready task. Multiple authorized tasks may be completed in one Session.

After each atomic task, validate its acceptance criteria, update `passes` and
`progress.txt`, and create a task-scoped Git checkpoint when safe. Continue after
a successful checkpoint without waiting for user confirmation or exiting.

Stop only when all tasks authorized for this run are complete, or a critical
blocker cannot be resolved within the authorized scope. Never repeat a verified
completed task. The Initializer still runs only once.

If validation fails, record the failure and leave `passes: false`.

If context is compacted, a Session is interrupted, or the process crashes,
resume from the persisted task state, actual artifacts, validation evidence, and
Git history. Do not blindly rerun completed or non-idempotent operations.

Never automatically start a new phase without explicit user authorization.

## 3. Persistent State

The following files are the recovery sources of truth:

- `feature-list.json`: task definitions, dependencies, acceptance criteria, and verified pass status.
- `progress.txt`: current task, completed work, test results, blockers, decisions, and exact next action.
- `git log`: committed implementation and checkpoint history.
- `init.sh`: repeatable environment and repository checks; it must not reset, delete, or overwrite user data.

Keep these files synchronized after each verifiable checkpoint.

If they conflict, inspect the repository and validation evidence before updating the recorded state.

## 4. Context Compaction Priority

When compacting context, preserve information in this order:

1. **Architecture decisions:** preserve verbatim; never summarize or discard.
2. **Modified files and critical changes.**
3. **Verification status:** PASS/FAIL, commands, and evidence references.
4. **Unresolved TODOs, blockers, and rollback notes.**
5. **Tool outputs:** may be discarded after preserving relevant conclusions and evidence locations.

Write essential state to persistent files before context compaction.

Do not rely on conversation history as the only source of project state.

## 5. Engineering and Safety Rules

- Inspect existing implementations and tests before modifying code.
- Keep changes limited to the current authorized task.
- Prefer existing project components over unnecessary new dependencies.
- Never fabricate test results or mark unverified work as complete.
- Preserve unrelated and uncommitted changes.
- Do not use destructive Git commands.
- Never commit credentials, `.env` secrets, personal data, or sensitive traces.
- Report changed files, validation results, blockers, and the next action at the end of each session.
