"""Real socket authentication with production verifier; SQLite/mock LLM only."""

import json
import os
from datetime import UTC, datetime

import pytest

from research.docs.agent_engineering_upgrade.p4_api_e2e.runner import HttpRun
from research.docs.agent_engineering_upgrade.p4_dependency_integration.manage import HERE, save
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

CASES = [
    "missing",
    "invalid",
    "expired",
    "revoked",
    "duplicate",
    "wrong_scheme",
    "spoof_body",
    "spoof_header",
    "default_subject",
    "compatible_body",
    "cross_owner",
    "cross_session",
    "user_admin_denied",
    "admin_allowed",
    "legacy_admin_header_denied",
    "sse_missing",
    "sse_invalid",
    "sse_valid",
    "unknown_session",
    "token_privacy",
]


@pytest.fixture(scope="module")
def auth_server():
    run = HttpRun(
        os.environ.get("P4B_AUTH_RUN_ID") or datetime.now(UTC).strftime("auth_%Y%m%d_%H%M%S"),
        run_root=HERE,
        worker_module="research.docs.agent_engineering_upgrade.p4_dependency_integration.worker",
        matrix_file=HERE / "test_auth_http.py",
    )
    run.outcomes = []
    try:
        run.start()
        manifest = json.loads((run.directory / "startup.json").read_bytes())
        assert manifest["auth_mode"] == "required" and manifest["legacy_auth"] is False
        yield run
    finally:
        run.stop()
        save(
            run.directory / "auth_results.json",
            dict(
                transport="REAL_TCP_UVICORN",
                verifier="PRODUCTION_AUTHENTICATOR",
                legacy=False,
                provider="CONTROLLED_MOCK_LLM",
                database="ISOLATED_SQLITE",
                passed=sum(r["status"] == "PASS" for r in run.outcomes),
                failed=sum(r["status"] == "FAIL" for r in run.outcomes),
                cases=len(run.outcomes),
                outcomes=run.outcomes,
                new_paid_calls=0,
            ),
        )


def header(kind="user"):
    return {"authorization": "Bearer " + TOKENS[kind]}


def api(run, case, *, token="user", payload=None, path="/api/v1/chat", headers=None, stream=False):
    return run.request(
        case,
        "POST",
        path,
        payload or dict(message="查询 ORD10001 的订单状态和金额"),
        headers=header(token) if headers is None else headers,
        stream=stream,
    )


@pytest.mark.parametrize("name", CASES)
def test_required_auth_real_http(auth_server, name):
    run = auth_server
    try:
        verify(run, name)
    except Exception as exc:
        run.outcomes.append(
            dict(case=name, status="FAIL", error_type=type(exc).__name__, reason=str(exc))
        )
        raise
    else:
        run.outcomes.append(dict(case=name, status="PASS"))


def verify(run, name):
    if name in {
        "missing",
        "invalid",
        "expired",
        "revoked",
        "wrong_scheme",
        "duplicate",
        "legacy_admin_header_denied",
        "sse_missing",
        "sse_invalid",
    }:
        headers = (
            header(name)
            if name in {"expired", "revoked"}
            else {}
            if name in {"missing", "sse_missing"}
            else {"authorization": "Bearer " + "z" * 43}
        )
        if name == "wrong_scheme":
            headers = {"authorization": "Basic " + TOKENS["user"]}
        if name == "duplicate":
            headers = [
                ("authorization", "Bearer " + TOKENS["user"]),
                ("authorization", "Bearer " + TOKENS["other"]),
            ]
        if name == "legacy_admin_header_denied":
            headers = {"x-admin-token": "p4-synthetic-admin"}
        row = api(
            run,
            name,
            headers=headers,
            path="/api/v1/chat/stream" if name.startswith("sse") else "/api/v1/chat",
        )
        assert row["status"] == 401 and row["body"]["error_code"] == "UNAUTHORIZED"
        assert row["database_before"] == row["database_after"]
        assert not any(e["kind"] == "model_started" for e in row["events"])
        return
    if name == "spoof_body":
        row = api(run, name, payload=dict(message="查询 ORD10001 状态", user_id="u_other"))
        assert row["status"] == 403 and row["database_before"] == row["database_after"]
        return
    if name == "spoof_header":
        row = api(
            run,
            name,
            headers=header() | {"x-user-id": "u_other", "x-authenticated-user": "u_other"},
        )
    elif name == "compatible_body":
        row = api(run, name, payload=dict(message="查询 ORD10001 状态", user_id="u_demo"))
    elif name == "cross_owner":
        row = api(run, name, token="other")
        assert (
            row["status"] == 200
            and "299.00" not in row["body"]["answer"]
            and "已发货" not in row["body"]["answer"]
        )
        return
    elif name == "cross_session":
        first = api(run, name + "_owner")
        row = api(
            run,
            name,
            token="other",
            payload=dict(message="继续查询", session_id=first["body"]["session_id"]),
        )
        assert row["status"] == 400 and row["database_before"] == row["database_after"]
        return
    elif name in {"user_admin_denied", "admin_allowed"}:
        row = run.request(
            name,
            "GET",
            "/api/v1/admin/tools",
            headers=header("admin" if name == "admin_allowed" else "user")
            | {"x-admin-token": "p4-synthetic-admin"},
        )
        assert row["status"] == (200 if name == "admin_allowed" else 403)
        return
    elif name == "sse_valid":
        row = api(run, name, path="/api/v1/chat/stream", stream=True)
        assert row["status"] == 200 and row["body"][-1]["event"] == "done"
        final = next(i["data"] for i in row["body"] if i["event"] == "answer")
        assert "299.00" in final["answer"]
        return
    elif name == "unknown_session":
        row = api(run, name, payload=dict(message="你好", session_id="p4b-unique-session"))
        assert row["status"] == 200
    else:
        row = api(run, name)
    assert row["status"] == 200
    session = next(
        s for s in row["database_after"]["sessions"] if s["session_id"] == row["body"]["session_id"]
    )
    assert session["user_id"] == "u_demo"
    if name != "unknown_session":
        assert "已发货" in row["body"]["answer"]
    assert all(token not in json.dumps(row, ensure_ascii=False) for token in TOKENS.values())
