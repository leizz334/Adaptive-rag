# Windows failure and fix record

All failures below are engineering/test infrastructure observations. None is a DeepSeek quality failure; no new model request was made.

| Finding | First evidence | Resolution and verified scope |
|---|---|---|
| Client-supplied user_id was the historical identity boundary | P4-A frozen auth BLOCKED; B0 19RED cases | Required opaque digest credential verifier, server subject binding, expiry/revocation/adminrole. 20 real TCP required-auth cases and independent33counterexamples. Historical legacy fixture is explicitly testing-only. |
| Credential provisioner Pydantic argument annotation | Mypy diagnostic | model_validate keeps runtime validation without suppressing the argument type. Mypy150files passes. |
| SSE TestClient global event reused across event loops | Combined auth/old API check, 56PASS1FAIL | Independent review fixture now restores AppStatus.should_exit_event through monkeypatch; 57combinedPASS. Production SSE unchanged. |
| Async Alembic URL failed with MissingGreenlet | b1_sandbox_red.xml | Async engine/run_sync path and supplied-connection support; independentSQLite upgrade→base→head succeeds. Real PostgreSQL NOT_RUN. Historical migration bodies unchanged. |
| Foreign exact-name Docker volumes could be adopted | b1_independent_review_safe_red.xml | Check every expected volume regardless partial containers; require owner/project labels. No Docker execution. |
| Ambient Compose variables/context could redirect targets | Independent review RED | Explicit child environment; local Unix socket; manifest/compose hash validation. Offline command recording verifies. |
| Partial project could point at unrelated local Redis/Qdrant | Independent source finding + counterexamples | Full3service ownership, static+actual loopback port, running state and data mount checks before direct backend access. |
| Repeated migration roundtrip could delete test data | Independent source finding | Fresh empty DB only; successful marker makes resume upgrade-only; unknown/nonempty state refuses and preserves data. Offline migration-control tests verify. |
| Harness snapshot/partial event errors could mask HTTP failure | b1_live_evidence_red.xml; b1_live_corrupt_red.xml | Persist partial HTTP/capture metadata, reject malformed/non-object/truncatedUTF8 events, retain original transport exception. Eight offline tests and independent probes. Actual Docker API path remains NOT_RUN. |
| Two HTTP200 no-ops could pass concurrency probe | Independent no-op double | Require paid→cancelled, one linked audit and matching confirmed-action idempotency record/output, preserve concurrency evidence on parse/snapshot errors. Not evidence distributed HITL works today. |
| RAG could pass using only fallback BM25/cache | Independent source finding | Cold-cache RAG requires successful retrieval.vector span and actual Redis keyTTL observations. Prepared, not executed against services. HTTP dependency-outage acceptance deferred B3. |
| P2-Q test fixture assumed Settings was still P2-frozen | windows_all_pytest.xml:785PASS1FAIL28SKIP | Only the mocked fixture now chooses unchanged app/providers/base.py for its baseline guard. Production frozen-source guard, old experimental results/Gold unchanged; replay/budget/tamper assertions still pass. |
| New standalone test imports hit existing eager import cycle | b1_contracts_green.xml:collectionERROR | Integration tests bootstrap the existing actual app entrypoint before component imports. No unrelated import-architecture rewrite; rerun18PASS. |
| Pytest file-path import gave no package for relative imports | Initial live-suite collection diagnostic | Prepared test modules use absolute namespace imports and full module CLI name.27tests collect/skip correctly on Windows. |

Initial formatting and reviewer scratch-parent errors are retained as diagnostic evidence. A credential-bearing scratch repr in an early reviewer RED artifact was explicitly redacted; the safe RED rerun and fixture repr protection preserve the substantive failure without exporting generated credentials. Later exact export scan must pass. No failed run/evidence file is silently overwritten.

Known real-dependency risks remain unverified: repository read-then-insert idempotency races, process-local pending confirmation, Redis rate-limit concurrency semantics/fail-open, actual PostgreSQL migrations/restart and Qdrant service behavior. They are acceptance probes for B2/B3, not waived tests or Windows PASS claims.
