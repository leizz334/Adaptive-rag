# B2 actual Ubuntu acceptance

Restored verified branch HEAD 11c81934e83b6a8930e82794000d6a99f27dc966, B1 ancestor 6924c5dfc37c945eb55b870c13a83b2d46929cd4. Independent Linux Python3.12.9 .venv; versions/image IDs/public sandbox metadata in ubuntu_20261111_environment.json and ubuntu_20261111_sandbox_public.json.

First real run: 7 PASS, 1 FAIL, 4 ERROR (ubuntu_B2_FIRST_20261111.xml). Concurrent repository writes raised PostgreSQL unique violation. Qdrant errors were environmental: ambient socks:// proxy scheme rejected by HTTPX; loopback with trust_env=False returned200. Subsequent test processes remove all *_proxy variables; worker environment was already sanitized. No production vector behavior changed.

Changed concurrency barrier to precede put+commit: atomic ON CONFLICT may wait for competing commit, so an after-put barrier would artificially deadlock valid implementations. Adjusted pre-fix run ubuntu_B2_RED_20261111.xml unexpectedly passed12/12; the race depends on scheduling. This run is not claimed RED. Original first-run failure is retained.

Minimal application fix uses PostgreSQL/SQLite INSERT ON CONFLICT DO NOTHING and fingerprint verification; first response persists and conflicting fingerprints still yield409. Final acceptance ubuntu_B2_FINAL_20261111.xml: 17 PASS,0FAIL,0ERROR,0SKIP (13 real dependency tests +4 existing SQLite transaction tests). Additional mismatch/first-response check passes. Real migrations upgrade/base/head on fresh owned DB, independent connections, rollback, Redis TTL/limiter/outage/recovery, Qdrant native filters/index/dimension errors and persistent restart all verified. Migration marker retained; no destructive roundtrip repeats. Ruff/format and Mypy150 PASS.

After user interruption/environment permission change, three owned containers were found exited255; existing mysql running, image IDs unchanged. Resume uses guarded start, preserving volumes and migration marker. No prior test failure erased.

No paid model calls or Experience Active. Native Qdrant checks do not claim tenant isolation; Redis limiter retains documented outage fail-open. B3 distributed HITL/API acceptance remains unverified until separate checkpoint.
