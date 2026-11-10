"""Server-provisioned opaque Bearer credentials; no client identity assertions."""

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.core.exceptions import ToolPermissionError, UnauthorizedError
from app.schemas.chat import ChatRequest


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    subject: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    roles: frozenset[Literal["user", "admin"]] = Field(min_length=1, max_length=2)
    expires_at: datetime
    not_before: datetime | None = None
    revoked: StrictBool = False

    @model_validator(mode="after")
    def bounds(self):
        if self.subject == "anonymous":
            raise ValueError("Reserved subject")
        for value in (self.expires_at, self.not_before):
            if value is not None and (value.tzinfo is None or value.utcoffset() != timedelta(0)):
                raise ValueError("UTC credential times required")
        if self.not_before is not None and self.not_before >= self.expires_at:
            raise ValueError("Credential interval invalid")
        return self


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate registry key")
        value[key] = item
    return value


class Authenticator:
    def __init__(self, raw: str, *, clock: Callable[[], datetime] | None = None, legacy=False):
        self.clock = clock or (lambda: datetime.now(UTC))
        self.legacy = legacy
        self.credentials: tuple[Credential, ...] = ()
        if not raw:
            return  # Required mode with an empty registry denies all business access.
        try:
            if len(raw.encode()) > 128_000:
                raise ValueError("Oversized registry")
            value = json.loads(raw, object_pairs_hook=_unique_object)
            if (
                not isinstance(value, dict)
                or set(value) != {"version", "credentials"}
                or type(value["version"]) is not int
                or value["version"] != 1
            ):
                raise ValueError("Unsupported registry schema")
            rows = value["credentials"]
            if not isinstance(rows, list) or len(rows) > 256:
                raise ValueError("Registry bound exceeded")
            credentials = tuple(Credential.model_validate(row) for row in rows)
            if len({row.token_sha256 for row in credentials}) != len(credentials):
                raise ValueError("Duplicate credential digest")
            self.credentials = credentials
        except Exception:
            # Never expose registry text, subject mappings or incoming credentials.
            raise ValueError("invalid credential registry") from None

    @classmethod
    def from_settings(cls, settings):
        if settings.auth_mode == "legacy_test" and settings.app_env != "testing":
            raise ValueError("legacy_test authentication is restricted to testing")
        return cls(
            settings.auth_credentials.get_secret_value(), legacy=settings.auth_mode == "legacy_test"
        )

    def authenticate(self, headers: list[str]) -> Principal | None:
        if self.legacy:
            return None
        if len(headers) != 1:
            raise UnauthorizedError("Bearer authentication required")
        matched = re.fullmatch(r"(?i:Bearer) ([A-Za-z0-9_-]{43,128})", headers[0])
        if matched is None:
            raise UnauthorizedError("invalid or expired credential")
        digest = hashlib.sha256(matched.group(1).encode("ascii")).hexdigest()
        now = self.clock()
        for credential in self.credentials:
            if hmac.compare_digest(credential.token_sha256, digest):
                if (
                    credential.revoked
                    or credential.expires_at <= now
                    or (credential.not_before is not None and credential.not_before > now)
                ):
                    break
                return Principal(credential.subject, frozenset(credential.roles))
        raise UnauthorizedError("invalid or expired credential")


def bind_identity(payload: ChatRequest, principal: Principal | None) -> ChatRequest:
    if principal is None:  # Only an explicitly configured isolated legacy test app.
        return payload
    if payload.user_id not in {"anonymous", principal.subject}:
        raise ToolPermissionError("request identity does not match authenticated subject")
    return payload.model_copy(update={"user_id": principal.subject})


def mint_credential(subject: str, expires_at: datetime, roles: list[str]) -> dict:
    """Trusted local operator only. Raw token is returned once, never stored here."""
    token = secrets.token_urlsafe(32)
    row = Credential.model_validate(
        dict(
            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            subject=subject,
            roles=roles,
            expires_at=expires_at,
        )
    )
    if row.expires_at <= datetime.now(UTC):
        raise ValueError("Future credential expiry required")
    return dict(bearer_token=token, registry_entry=row.model_dump(mode="json"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Trusted local provisioning; protect output and never commit raw tokens"
    )
    parser.add_argument("--subject", required=True)
    parser.add_argument("--expires-at", required=True, help="UTC ISO timestamp")
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            mint_credential(
                args.subject,
                datetime.fromisoformat(args.expires_at),
                ["admin"] if args.admin else ["user"],
            )
        )
    )
