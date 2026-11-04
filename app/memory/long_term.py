"""Isolated in-memory preference prototype; no HTTP identity or production wiring."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class MemoryIdentity:
    """Server-injected authentication assertion, never constructed from ChatRequest.user_id."""

    tenant_id: str
    user_id: str
    verified: bool = False


_REQUEST_IDENTITY: ContextVar[MemoryIdentity | None] = ContextVar(
    "verified_memory_identity", default=None
)


def current_memory_identity() -> MemoryIdentity | None:
    return _REQUEST_IDENTITY.get()


@contextmanager
def verified_memory_scope(identity: MemoryIdentity):
    """Only trusted server middleware/test harness may set this task-local assertion."""
    if identity.verified is not True or not identity.tenant_id or not identity.user_id:
        raise PermissionError("Verified request identity required")
    token = _REQUEST_IDENTITY.set(identity)
    try:
        yield
    finally:
        _REQUEST_IDENTITY.reset(token)


@dataclass(frozen=True)
class PreferenceRecord:
    tenant_id: str
    user_id: str
    key: str
    value: str
    source: str
    version: int
    updated_at: float
    expires_at: float
    valid: bool = True


ALLOWED_PREFERENCES = {
    "language": {"zh-CN", "en", "ja"},
    "tone": {"brief", "detailed", "formal", "friendly"},
    "response_style": {"concise", "step_by_step"},
}


class PreferenceMemory:
    """No vector index/cache/backups; delete/revoke physically discard stored values."""

    def __init__(self, *, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._consent: dict[tuple[str, str], tuple[bool, str]] = {}
        self._records: dict[tuple[str, str, str], PreferenceRecord] = {}
        self._versions: dict[tuple[str, str, str], int] = {}

    @staticmethod
    def _scope(identity: MemoryIdentity) -> tuple[str, str]:
        if identity.verified is not True or not identity.tenant_id or not identity.user_id:
            raise PermissionError("Verified server identity required")
        return identity.tenant_id, identity.user_id

    @staticmethod
    def _source(source: str):
        if not source.strip() or len(source) > 128:
            raise ValueError("Bounded provenance source required")

    def set_consent(self, identity: MemoryIdentity, granted: bool, *, source: str):
        scope = self._scope(identity)
        if type(granted) is not bool:
            raise ValueError("Explicit boolean consent required")
        self._source(source)
        self._consent[scope] = granted, source
        if not granted:
            for key in list(self._records):
                if key[:2] == scope:
                    del self._records[key]
                    self._versions[key] = self._versions.get(key, 0) + 1

    def upsert(
        self,
        identity: MemoryIdentity,
        key: str,
        value: str,
        *,
        source: str,
        ttl_seconds: int = 86400,
        expected_version: int | None = None,
    ) -> PreferenceRecord:
        scope = self._scope(identity)
        if not self._consent.get(scope, (False, ""))[0]:
            raise PermissionError("Explicit consent required")
        self._source(source)
        if key not in ALLOWED_PREFERENCES or value not in ALLOWED_PREFERENCES[key]:
            raise ValueError("Only enumerated stable preferences are supported")
        if not 0 < ttl_seconds <= 2592000:
            raise ValueError("Bounded positive expiry required")
        index = (*scope, key)
        version = self._versions.get(index, 0)
        if expected_version is not None and expected_version != version:
            raise ValueError("Memory version conflict")
        now = self._clock()
        record = PreferenceRecord(*scope, key, value, source, version + 1, now, now + ttl_seconds)
        self._records[index] = record
        self._versions[index] = record.version
        return record

    def recall(self, identity: MemoryIdentity) -> list[PreferenceRecord]:
        scope = self._scope(identity)
        if not self._consent.get(scope, (False, ""))[0]:
            return []
        return [
            r
            for key, r in self._records.items()
            if key[:2] == scope and r.valid and r.expires_at > self._clock()
        ]

    def invalidate(self, identity: MemoryIdentity, key: str):
        index = (*self._scope(identity), key)
        if index in self._records:
            value = self._records[index]
            self._records[index] = replace(
                value, valid=False, version=value.version + 1, updated_at=self._clock()
            )
            self._versions[index] = value.version + 1

    def delete(self, identity: MemoryIdentity, key: str):
        index = (*self._scope(identity), key)
        self._records.pop(index, None)
        self._versions[index] = self._versions.get(index, 0) + 1
