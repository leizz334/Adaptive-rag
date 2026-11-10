# Ubuntu recovery preflight

Local/remote branch codex/p4-dependency-integration exact HEAD 11c81934e83b6a8930e82794000d6a99f27dc966; B1 checkpoint 6924c5dfc37c945eb55b870c13a83b2d46929cd4 is present. Initial working tree clean.

Linux Python 3.12.9, independent .venv, installed pyproject dev extras; pip check PASS. System Python 3.10.12 is not used. Docker client 29.1.3, Engine 29.8.0. Compose initially missing; installed official v5.6.0 binary user-local with explicit approval. Socket access requires escalation in this harness. Existing mysql container and all existing volumes preserved.

First sandbox up timed out after 180s while pulling images, before creating any project containers. PostgreSQL image completed. Separate exact-image pulls started for Redis and Qdrant; no service acceptance has run. No application defect inferred.

Initial pip network denied in sandbox; authorized network retry. Operator moved the new environment during installation, causing missing interpreter; recreated at final ignored .venv path and successful reinstall.

Pre-change static checks: Ruff check PASS; format 325 files PASS; Mypy 150 source files PASS (four untyped-body notes). These are not real-service acceptance.

No paid requests, Experience Active off. No new worktree; no B0/B1 task replay.
