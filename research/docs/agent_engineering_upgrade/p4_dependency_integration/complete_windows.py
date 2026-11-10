"""Record only verified Windows B0/B1, then leave B2/B3 waiting for Ubuntu."""

import json
import xml.etree.ElementTree as ET

from . import manage as m


def read(path):
    return json.loads(path.read_bytes())


def main():
    target = m.HERE / "validation.json"
    if target.exists():
        raise FileExistsError("Resume recorded checkpoint; never repeat completed work")
    xml = m.HERE / "evidence/windows_all_pytest_verified.xml"
    suite = ET.parse(xml).getroot().find("testsuite")
    assert suite is not None
    passed = (
        int(suite.attrib["tests"])
        - int(suite.attrib["skipped"])
        - int(suite.attrib["failures"])
        - int(suite.attrib["errors"])
    )
    assert (
        passed,
        int(suite.attrib["skipped"]),
        int(suite.attrib["failures"]),
        int(suite.attrib["errors"]),
    ) == (794, 28, 0, 0)
    auth = read(m.HERE / "runs/20261110_B1_auth_final_03/auth_results.json")
    assert (auth["cases"], auth["passed"], auth["failed"]) == (20, 20, 0)
    legacy = read(m.HERE.parent / "p4_api_e2e/runs/20261110_B1_legacy_http_03/matrix_results.json")
    assert (legacy["scenarios"], legacy["passed"], legacy["failed"], legacy["blocked"]) == (
        42,
        41,
        0,
        1,
    )
    regression = read(m.HERE / "runs/20261110_B1_legacy_01/results.json")
    assert regression["regressions"] == []
    styles = read(m.HERE / "evidence/windows_style_final.json")
    assert all(r["exit_code"] == 0 for r in styles)
    audit = read(m.HERE / "evidence/windows_audit.json")
    assert audit["immutable_history_gold_preserved"] and audit["edited_csv_preserved"]
    review = read(m.HERE / "evidence/b1_live_harness_review.json")
    # Independently authored review evidence is preserved verbatim, not re-scored here.
    assert "PASS_BOUNDED_PREPARATION_REVIEW" in json.dumps(review)
    sources = {p.relative_to(m.ROOT).as_posix(): m.sha(p) for p in (m.ROOT / "app").rglob("*.py")}
    sources.update({p.relative_to(m.ROOT).as_posix(): m.sha(p) for p in m.HERE.glob("*.py")})
    sources["alembic/env.py"] = m.sha(m.ROOT / "alembic/env.py")
    sources["compose.integration.yml"] = m.sha(m.HERE / "compose.integration.yml")
    m.save(
        target,
        dict(
            phase="P4-B",
            environment="Windows",
            baseline=m.BASE,
            pytest_pass=passed,
            pytest_fail=0,
            pytest_errors=0,
            skipped_total=28,
            blocked_real_dependencies=27,
            historical_legacy_auth_probe_skipped=1,
            required_auth_tcp=dict(cases=20, passed=20, failed=0),
            legacy_tcp=dict(cases=42, passed=41, failed=0, blocked=1),
            regression_count=0,
            legacy_groups=regression["groups"],
            ruff_check="PASS",
            ruff_format="PASS",
            mypy="PASS_150_SOURCE_FILES",
            trusted_auth="PASS_BOUNDED_CREDENTIAL_SCHEME",
            postgresql="BLOCKED_WAITING_UBUNTU_NOT_RUN",
            redis="BLOCKED_WAITING_UBUNTU_NOT_RUN",
            qdrant="BLOCKED_WAITING_UBUNTU_NOT_RUN",
            real_dependency_api="BLOCKED_WAITING_UBUNTU_NOT_RUN",
            hitl_concurrency="NOT_RUN_KNOWN_RISK",
            http_backend_outage="DEFERRED_B3",
            paid_model_requests=0,
            billed_tokens=0,
            experience_active=False,
            no_new_worktree=True,
            source_hashes=sources,
        ),
    )
    m.checkpoint(
        "P4-B1",
        [
            "validation.json",
            "AUTH_SCHEME.md",
            "UBUNTU_RUNBOOK.md",
            "FAILURE_RECORD.md",
            "evidence/windows_all_pytest_verified.xml",
            "evidence/windows_style_final.json",
            "evidence/windows_audit.json",
            "evidence/b1_independent_review.json",
            "evidence/b1_live_harness_review.json",
            "runs/20261110_B1_legacy_01/results.json",
        ],
        f"{passed}PASS/0FAIL/28SKIP(27Ubuntu-deferred+1historicalauthprobe);Ruffcheck+formatPASS;Mypy150PASS;legacy214noPASS-to-FAIL;realrequired-authTCP20/20;PG/Redis/Qdrant/API27NOT_RUN",
        "Commit Windows B1;normalpush+lsremote;PAUSE WAITING_UBUNTU. Restore Ubuntu B2/B3 per UBUNTU_RUNBOOK.md; no paid/Active/P4-C",
        status="completed_windows_preparation",
    )
    state = read(m.STATE / "feature-list.json")
    phase = state["p4_dependency_integration"]
    phase.update(
        status="WINDOWS_COMPLETE_WAITING_UBUNTU",
        windows_phase_status="PARTIAL_PASS",
        authorized_now=[],
        resume_tasks=["P4-B2", "P4-B3"],
        actual_model_calls=0,
    )
    phase["tasks"][0].update(
        commit_hash=m.git("rev-parse", "146311c"),
        implementation_commit=m.git("rev-parse", "fdef173"),
    )
    m.save(m.STATE / "feature-list.json", state)
    report = f"""# P4-B Windows checkpoint: trusted authentication and dependency preparation

**PHASE_STATUS = PARTIAL_PASS; execution state = WAITING_UBUNTU.** Windows B0/B1 are verified and delivered. B2/B3 have not run. This is the user-requested handoff boundary, not full dependency acceptance.

## Identity and compatibility

The API now defaults to server-provisioned opaque Bearer credentials, stored as bounded SHA256 digest records with subject, roles, UTC validity and revocation. Both chat paths bind the verified subject before Graph/business dispatch; a conflicting client user_id is rejected. Admin metadata requires a verified admin role. Old x-admin-token cannot bypass required mode. Invalid/missing/expired/revoked credentials fail closed. Existing request/response body shapes and Owner/Session/HITL/idempotency checks remain.

Twenty real Uvicorn/TCP required-auth scenarios pass, including spoofing, cross-user orders/Sessions, admin and SSE. The production dependency is used; no fake principal injection occurs in that matrix. Thirty-three independent route/verifier counterexamples plus19auth unit and5legacy API checks pass together. Test credentials are intentionally public synthetic fixtures; deployment credentials must be privately provisioned by a trusted operator over TLS. This is a small real API-credential scheme, not a user registration/OAuth/human-identity platform. Client credential delivery, TLS and operator subject ownership remain deployment responsibilities; no authentication UI was built.

The historical P4-A fixture explicitly uses legacy_test only with app_env=testing. Startup forbids that mode in development/production. Its old authentication probe remains an unchanged historical BLOCKED/skip; it is not relabeled. Existing fixture compatibility does not count as trusted authentication.

## Real dependencies prepared, not executed

The isolated Compose configuration reuses the existing PostgreSQL16alpine/Redis7alpine/Qdrant1.12.5 image choices, unique project-scoped containers/volumes, private generated credentials and loopback ports. Docker mutations use only the local Unix socket with sanitized interpolation environment. Guard checks reject foreign exact-name volumes, partial/misbound service endpoints and unowned resources. No Docker services were started or stopped on Windows; Docker is absent from the current PATH.

Twelve B2 tests are prepared for real migrations, persistence, transactions, concurrent idempotency, cache/TTL/limiting, Qdrant retrieval/filter/index/errors and owned restart recovery. Fifteen B3 actual-dependency HTTP/SSE scenarios use two Uvicorn processes, required authentication, shared SQL-backed M2, RAG/tools and controlled model output. They require actual PostgreSQL/Redis/Qdrant backends and refuse startup memory degradation. Cold RAG additionally requires successful vector spans and Redis key/TTL proof. HTTP backend-outage API acceptance is explicitly deferred for B3 implementation/execution.

The existing sync-only Alembic environment failed on async URLs. Its minimal async/run_sync/supplied-connection adaptation passes a real isolated SQLite upgrade→base→head cycle and PostgreSQL DDL compilation. Historical migration bodies remain unchanged. A destructive initial roundtrip now requires a fresh empty owned DB; a successful marker makes resume upgrade-only. PostgreSQL runtime compatibility is still NOT_RUN, never inferred from SQLite.

Redis AsyncMock and Qdrant local :memory: roundtrips verify only local driver contracts. Twelve independent ownership/migration counterexamples pass. Eight local HTTP-evidence/concurrency false-pass controls pass; independent review closes all identified preparation findings. Source review and doubles do not validate actual Docker behavior or process cleanup on Ubuntu.

## Verification and evidence

- Full application + historical helper + real TCP suites: **{passed}passed,0failed/errors,28skipped**.27are pending Ubuntu service/API cases;1is the historical P4-A legacy auth probe. No skipped test is counted as PASS.
- Final required-auth TCP matrix:20/20. Final legacy matrix:41PASS/0FAIL/1historicalBLOCKED. Providers are controlled/mock, database SQLite; these are not real-dependency or DeepSeek results.
- Fresh214scripted legacy service cases: original80=80/80, old16=13/16, formerDevelopment30=30/30, formerBlind33=33/33, P2-SDevelopment24=23/24, P2-SHoldout30=22/30,long1/1. **Zero previous strict PASS→FAIL regressions.**
- Ruff check and format--check pass; Mypy150source files pass. One existing LangGraph pending-deprecation warning remains.
- Inventory checks2240prior tracked files,20root user files and edited human CSV. Only10explicitly authorized prior source/test files change; original reports/Gold/raw evidence and old task namespaces/progress prefix are preserved. New auth code/tests/artifacts are separate. Root user modifications and .env remain untouched. Export secret scan passes without recording secret values.

Initial failures remain in evidence/ and FAILURE_RECORD.md. The first expanded run785PASS1FAIL28SKIP exposed an old mocked P2-Q fixture that assumed Settings was unchanged. It now freezes the actually unchanged provider base interface; the original paid harness's source guard, old Gold and experiment results are unchanged. A subsequent792PASS run preceded two additional corrupt-event counterexamples; the final fresh suite above includes them. No test ID/Gold rule, Owner check or HITL budget was weakened.

Exact source hashes/configuration and dataset group results are in validation.json, startup manifests, JUnit, independent review and immutable runs. Compatibility rerun artifacts use new IDs under p4_api_e2e/runs/20261110_B1_legacy_http_*; original P4-A records are unchanged. Required-auth and214service runs are in this phase. Repeated diagnostic executions are not independent quality samples. Private DB/log/config files are not synchronized or committed.

## Outstanding and Ubuntu recovery

Real PostgreSQL/Redis/Qdrant/API E2E, actual service restart recovery and distributed HITL/idempotency are **BLOCKED_WAITING_UBUNTU / NOT_RUN**. Repository read-then-insert idempotency and process-local pending confirmation remain known risks with ordinary failing acceptance probes prepared; no Windows result certifies them. Redis outage fail-open is the existing documented availability policy, not strict throttling/authentication. Qdrant native filter checks do not claim application tenant vector isolation. Resolved image digests and actual Docker/package versions must be captured on Ubuntu.

Follow UBUNTU_RUNBOOK.md after verifying the pushed branch/commit. Generate new private credentials/DSNs locally, never copy .env or temporary DBs. Keep first failed evidence, repair only confirmed defects, checkpoint B2 then B3 and perform full final regression. No completed paid operation exists to repeat: **new paid model HTTP=0; billed tokens=0; cost=US$0**. External tracing and Experience Active remain off.

Windows B0 commits fdef173/146311c; B1/delivery exact hashes are recorded in state/Git/evidence/delivery.json and the final response. Ordinary push only to the authorized repository and codex/p4-dependency-integration. On network failure keep commits and use `git push origin HEAD:codex/p4-dependency-integration`; never redo tests merely to push. **PAUSE WAITING_UBUNTU; no P4-C/D/E.**
"""
    (m.HERE / "P4-B_FINAL_REPORT.md").write_text(report, encoding="utf8")
    with (m.HERE / "RECOVERY.md").open("a", encoding="utf8") as f:
        f.write(
            f"\nWINDOWS_VERIFIED:full{passed}PASS0FAIL28SKIP/Ruffcheck+formatPASS/Mypy150PASS;legacy2140regressions;auth20PASS. validation.json/report are final evidence. B1prepared;B2/B3passesFalse waiting_ubuntu. NextONLYB1commit/push/lsremote/deliverymetadata/PAUSE. No new services/paid/Active/P4C.\n"
        )
    print(f"Recorded Windows B0/B1: {passed} PASS; PAUSE WAITING_UBUNTU after commit/push")


if __name__ == "__main__":
    main()
