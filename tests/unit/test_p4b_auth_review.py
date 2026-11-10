"""Independent offline B0 counterexamples; real verifier, no fake principals.

ASGI transport deliberately skips application lifespan/database initialization.
Only the business container is replaced, to observe whether rejected requests
reach a service. Real TCP/Uvicorn and dependency validation belong elsewhere.
"""

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sse_starlette.sse import AppStatus

from app.api.dependencies import get_container
from app.config.settings import Settings
from app.core.auth import Authenticator, mint_credential
from app.core.exceptions import UnauthorizedError
from app.main import create_app
from app.schemas.chat import ChatResponse

NOW = datetime(2026, 11, 10, tzinfo=UTC)
USER_TOKEN = "review_user_" + "a" * 43
ADMIN_TOKEN = "review_admin_" + "b" * 43


def _row(token=USER_TOKEN, subject="review_user", roles=None, **changes):
    result = {
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "subject": subject,
        "roles": roles or ["user"],
        "expires_at": "2026-11-11T00:00:00Z",
    }
    result.update(changes)
    return result


def _registry(*rows):
    return json.dumps({"version": 1, "credentials": list(rows)})


@pytest.fixture(autouse=True)
def _no_network(event_loop, monkeypatch):
    # Windows constructs its event-loop wakeup socketpair with a loopback
    # connect. Build that framework fixture before prohibiting test traffic,
    # and restore sockets before pytest tears the event loop down.
    def forbidden(*args, **kwargs):
        raise AssertionError("independent auth tests must remain offline")

    with monkeypatch.context() as patches:
        patches.setattr(AppStatus, "should_exit_event", None)
        patches.setattr(socket, "create_connection", forbidden)
        patches.setattr(socket.socket, "connect", forbidden)
        patches.setattr(socket.socket, "connect_ex", forbidden)
        yield


class RecordingService:
    def __init__(self):
        self.calls = []
        self.registry = SimpleNamespace(names=lambda: ["review_marker"])

    async def chat(self, payload, *, trace_id):
        self.calls.append(("chat", payload))
        return ChatResponse(answer="recorded", session_id="review_session", trace_id=trace_id)

    async def stream(self, payload, *, trace_id):
        self.calls.append(("stream", payload))
        yield {"event": "done", "trace_id": trace_id}


@pytest.fixture
async def boundary():
    registry = _registry(_row(), _row(ADMIN_TOKEN, "review_admin", ["admin"]))
    settings = Settings(
        _env_file=None,
        app_env="production",
        auth_mode="required",
        auth_credentials=registry,
        admin_api_token="synthetic_obsolete_admin_token",
    )
    application = create_app(settings)
    application.state.authenticator.clock = lambda: NOW
    service = RecordingService()
    container = SimpleNamespace(settings=settings, chat_service=service)
    application.dependency_overrides[get_container] = lambda: container
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://offline.test"
    ) as client:
        yield client, service


@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("x-user-id", "review_user"), ("x-forwarded-user", "review_user")],
        [("authorization", "Bearer " + USER_TOKEN + ", Bearer " + ADMIN_TOKEN)],
        [("authorization", "Bearer " + USER_TOKEN), ("Authorization", "Bearer " + ADMIN_TOKEN)],
        [("authorization", "Bearer\t" + USER_TOKEN)],
        [("authorization", "Bearer " + USER_TOKEN + " ")],
        [("authorization", "Bearer " + "z" * 129)],
    ],
    ids=["missing", "proxy-identity", "combined", "duplicate", "tab", "trailing", "oversize"],
)
async def test_chat_and_sse_reject_header_bypasses_before_service(boundary, path, headers):
    client, service = boundary
    response = await client.post(path, headers=headers, json={"message": "query"})
    assert response.status_code == 401
    assert service.calls == []
    assert USER_TOKEN not in response.text and ADMIN_TOKEN not in response.text


@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
async def test_chat_and_sse_bind_server_subject_and_reject_body_spoof(boundary, path):
    client, service = boundary
    headers = {"authorization": "Bearer " + USER_TOKEN, "x-user-id": "review_admin"}
    rejected = await client.post(
        path, headers=headers, json={"message": "query", "user_id": "review_admin"}
    )
    assert rejected.status_code == 403
    assert service.calls == []
    accepted = await client.post(
        path,
        headers=headers,
        json={"message": "query", "roles": ["admin"], "subject": "review_admin"},
    )
    assert accepted.status_code == 200
    assert len(service.calls) == 1
    assert service.calls[0][1].user_id == "review_user"


@pytest.mark.parametrize("path", ["/api/v1/admin/tools", "/api/v1/admin/skills"])
async def test_admin_rejects_old_token_and_client_role_headers(boundary, path):
    client, _ = boundary
    old = {"x-admin-token": "synthetic_obsolete_admin_token", "x-roles": "admin"}
    assert (await client.get(path, headers=old)).status_code == 401
    old["authorization"] = "Bearer " + USER_TOKEN
    assert (await client.get(path, headers=old)).status_code == 403
    assert (
        await client.get(path, headers={"authorization": "Bearer " + ADMIN_TOKEN})
    ).status_code == 200


async def test_health_stays_public_and_does_not_dispatch_business_work(boundary):
    client, service = boundary
    assert (await client.get("/api/v1/health")).status_code == 200
    assert service.calls == []


def test_not_before_and_expiry_use_closed_open_interval_each_request():
    moment = [NOW - timedelta(microseconds=1)]
    auth = Authenticator(
        _registry(_row(not_before=NOW.isoformat(), expires_at=(NOW + timedelta(seconds=1)).isoformat())),
        clock=lambda: moment[0],
    )
    with pytest.raises(UnauthorizedError):
        auth.authenticate(["Bearer " + USER_TOKEN])
    moment[0] = NOW
    assert auth.authenticate(["Bearer " + USER_TOKEN]).subject == "review_user"
    moment[0] = NOW + timedelta(seconds=1)
    with pytest.raises(UnauthorizedError):
        auth.authenticate(["Bearer " + USER_TOKEN])


@pytest.mark.parametrize(
    "changes",
    [
        {"expires_at": "2026-11-11T08:00:00+08:00"},
        {"not_before": "2026-11-09T00:00:00"},
        {"not_before": "2026-11-11T00:00:00Z"},
        {"revoked": 0},
        {"roles": ["USER"]},
        {"unexpected": "synthetic_private_marker"},
    ],
    ids=["non-utc", "naive", "empty-interval", "coerced-revocation", "unknown-role", "extra"],
)
def test_bad_registry_is_rejected_without_disclosing_inputs(changes):
    raw = _registry(_row(**changes))
    with pytest.raises(ValueError) as caught:
        Authenticator(raw)
    assert str(caught.value) == "invalid credential registry"
    assert raw not in str(caught.value)


@pytest.mark.parametrize("raw", [
    _registry(_row(), _row(subject="review_admin", roles=["admin"])),
    _registry(*[_row(token=f"synthetic_{i}_" + "x" * 43) for i in range(257)]),
    '{"version":true,"credentials":[]}',
    '{"version":1,"credentials":[{"subject":"first","subject":"last"}]}',
    " " * 128_001,
], ids=["duplicate-digest", "row-limit", "bool-version", "duplicate-nested-key", "byte-limit"])
def test_registry_ambiguity_and_bounds_fail_closed(raw):
    with pytest.raises(ValueError, match="^invalid credential registry$"):
        Authenticator(raw)


def test_testing_does_not_implicitly_disable_authentication():
    settings = Settings(_env_file=None, app_env="testing", auth_credentials="")
    auth = Authenticator.from_settings(settings)
    assert auth.legacy is False
    with pytest.raises(UnauthorizedError):
        auth.authenticate([])


def test_server_mint_round_trip_stores_hash_only():
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    issued = mint_credential("synthetic_minted_user", expiry, ["user"])
    token = issued["bearer_token"]
    assert len(token) >= 43
    entry = issued["registry_entry"]
    assert token not in json.dumps(entry)
    identity = Authenticator(_registry(entry)).authenticate(["Bearer " + token])
    assert identity.subject == "synthetic_minted_user"
    assert identity.roles == frozenset({"user"})
