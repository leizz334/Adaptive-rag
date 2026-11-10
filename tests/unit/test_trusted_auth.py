import hashlib
import importlib
import json
from datetime import UTC, datetime

import pytest

from app.config.settings import Settings
from app.core.exceptions import ToolPermissionError, UnauthorizedError
from app.schemas.chat import ChatRequest

NOW = datetime(2026, 11, 10, tzinfo=UTC)
TOKEN = "a" * 43


def api():
    return importlib.import_module("app.core.auth")


def registry(**changes):
    entry = dict(
        token_sha256=hashlib.sha256(TOKEN.encode()).hexdigest(),
        subject="u_demo",
        roles=["user"],
        expires_at="2026-11-11T00:00:00+00:00",
        revoked=False,
    )
    entry.update(changes)
    return json.dumps(dict(version=1, credentials=[entry]))


def test_verified_subject_replaces_omitted_client_identity_without_mutation():
    auth = api().Authenticator(registry(), clock=lambda: NOW)
    identity = auth.authenticate(["Bearer " + TOKEN])
    original = ChatRequest(message="query")
    bound = api().bind_identity(original, identity)
    assert bound.user_id == "u_demo" and original.user_id == "anonymous"
    assert "admin" not in identity.roles
    with pytest.raises(ToolPermissionError):
        api().bind_identity(ChatRequest(message="query", user_id="other"), identity)


@pytest.mark.parametrize(
    "headers",
    [
        [],
        ["Bearer " + "b" * 43],
        ["Basic " + TOKEN],
        ["Bearer x"],
        ["Bearer " + TOKEN, "Bearer " + TOKEN],
        ["Bearer " + TOKEN + " extra"],
        ["Bearer aa.bb.cc"],
    ],
)
def test_missing_forged_malformed_and_duplicate_credentials_fail_closed(headers):
    with pytest.raises(UnauthorizedError):
        api().Authenticator(registry(), clock=lambda: NOW).authenticate(headers)


@pytest.mark.parametrize(
    "changes",
    [
        dict(expires_at="2026-11-10T00:00:00Z"),
        dict(revoked=True),
        dict(not_before="2026-11-10T01:00:00Z"),
    ],
)
def test_expired_revoked_and_not_yet_valid_credentials_rejected(changes):
    with pytest.raises(UnauthorizedError):
        api().Authenticator(registry(**changes), clock=lambda: NOW).authenticate(
            ["Bearer " + TOKEN]
        )


@pytest.mark.parametrize(
    "raw",
    [
        registry(roles=["superadmin"]),
        registry(revoked="false"),
        registry(subject="anonymous"),
        registry(expires_at="2026-11-11"),
        registry(token_sha256="not-digest"),
        '{"version":1,"version":1,"credentials":[]}',
    ],
)
def test_invalid_registry_and_duplicate_json_keys_are_rejected_safely(raw):
    with pytest.raises(ValueError, match="credential registry"):
        api().Authenticator(raw)


def test_default_required_and_no_legacy_mode_in_production():
    assert Settings(_env_file=None).auth_mode == "required"
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production", auth_mode="legacy_test")
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="development", auth_mode="legacy_test")


def test_admin_only_server_role_and_empty_registry_fails_closed():
    identity = (
        api()
        .Authenticator(registry(roles=["admin"]), clock=lambda: NOW)
        .authenticate(["bEaReR " + TOKEN])
    )
    assert identity.roles == frozenset({"admin"})
    with pytest.raises(UnauthorizedError):
        api().Authenticator("").authenticate(["Bearer " + TOKEN])
