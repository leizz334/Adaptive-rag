"""Isolated relational experience governance; no business schema integration."""

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import (
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    delete,
    inspect,
    select,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.security import mask_pii
from app.experience.contracts import ExperienceScope
from app.experience.reflection import ExperienceCandidate


class ExperienceBase(DeclarativeBase):
    pass


class ExperienceRow(ExperienceBase):
    __tablename__ = "experience_shadow_records"
    __table_args__ = (UniqueConstraint("tenant_ref", "user_ref", "session_ref", "fingerprint"),)
    experience_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_ref: Mapped[str] = mapped_column(String(64), index=True)
    user_ref: Mapped[str] = mapped_column(String(64), index=True)
    session_ref: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(Text)


class ExperienceEventRow(ExperienceBase):
    __tablename__ = "experience_shadow_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experience_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    evidence_ref: Mapped[str] = mapped_column(Text, default="")


class ExperienceTombstoneRow(ExperienceBase):
    __tablename__ = "experience_shadow_tombstones"
    __table_args__ = (UniqueConstraint("tenant_ref", "user_ref", "session_ref", "fingerprint"),)
    experience_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_ref: Mapped[str] = mapped_column(String(64))
    user_ref: Mapped[str] = mapped_column(String(64))
    session_ref: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[str] = mapped_column(String(40))


async def initialize_schema(engine, *, isolated=False):
    if isolated is not True or engine.dialect.name != "sqlite":
        raise ValueError("Explicit isolated SQLite only; production migration is not enabled")
    async with engine.begin() as connection:
        names = await connection.run_sync(lambda c: inspect(c).get_table_names())
        if set(names) - set(ExperienceBase.metadata.tables):
            raise ValueError("Experience storage cannot initialize a business database")
        await connection.run_sync(ExperienceBase.metadata.create_all)


async def drop_schema(engine, *, isolated=False):
    if isolated is not True or engine.dialect.name != "sqlite":
        raise ValueError("Explicit isolated SQLite only")
    async with engine.begin() as connection:
        await connection.run_sync(ExperienceBase.metadata.drop_all)


def _scope(scope):
    value = ExperienceScope.model_validate(scope.model_dump())
    value.require_verified()
    return value


def _filter(table, scope):
    return and_(
        table.tenant_ref == scope.tenant_ref,
        table.user_ref == scope.user_ref,
        table.session_ref == scope.session_ref,
    )


def _privacy(candidate):
    identifiers = [candidate.source_trace_id, candidate.source_case_id]
    identifiers += [v for r in candidate.evidence_refs for v in (r.artifact, r.pointer)]
    for text in identifiers:
        if mask_pii(text) != text or re.search(
            r"(?:sk-[A-Za-z0-9_-]+|[\w.+-]+@[\w.-]+\.[A-Za-z]+|\bORD\d+\b|\bSKU-[A-Za-z0-9_-]+)",
            text,
            re.I,
        ):
            raise ValueError(
                "Sensitive identifiers must be replaced by opaque provenance references"
            )


class ExperienceRepository:
    """Owns independent transactions; no caller business session is accepted."""

    def __init__(self, factory, *, resolver, clock=None):
        self.factory, self.resolver = factory, resolver
        self.clock = clock or (lambda: datetime.now(UTC))

    def _event(self, session, row, action, evidence_ref=""):
        event_id = hashlib.sha256(
            f"{row.experience_id}:{row.version}:{action}:{evidence_ref}".encode()
        ).hexdigest()
        session.add(
            ExperienceEventRow(
                event_id=event_id,
                experience_id=row.experience_id,
                action=action,
                version=row.version,
                evidence_ref=evidence_ref,
            )
        )

    async def _write(self, session, row, value, *, action, evidence_ref=""):
        old_version = row.version
        payload = value.model_dump_json()
        result = await session.execute(
            update(ExperienceRow)
            .where(
                ExperienceRow.experience_id == row.experience_id,
                ExperienceRow.version == old_version,
            )
            .values(payload=payload, version=value.version)
        )
        if result.rowcount != 1:
            raise ValueError("Experience version conflict")
        row.version = value.version
        row.payload = payload
        self._event(session, row, action, evidence_ref)
        return value

    async def _expire(self, session, row):
        value = ExperienceCandidate.model_validate_json(row.payload)
        now = self.clock()
        if value.expires_at <= now and value.validation_status not in {"EXPIRED", "REJECTED"}:
            data = value.model_dump() | dict(
                validation_status="EXPIRED", updated_at=now, version=value.version + 1
            )
            value = ExperienceCandidate.model_validate(data)
            await self._write(session, row, value, action="EXPIRED")
        return value

    async def propose(self, scope, candidate):
        scope = _scope(scope)
        candidate = ExperienceCandidate.model_validate(candidate.model_dump())
        if candidate.scope.key != scope.key:
            raise PermissionError("Scope mismatch")
        _privacy(candidate)
        for ref in candidate.evidence_refs:
            self.resolver.resolve(ref)
        async with self.factory() as session, session.begin():
            deleted = await session.scalar(
                select(ExperienceTombstoneRow).where(
                    _filter(ExperienceTombstoneRow, scope),
                    ExperienceTombstoneRow.fingerprint == candidate.fingerprint,
                )
            )
            if deleted:
                raise ValueError("Deleted experience cannot be automatically reimported")
            row = await session.scalar(
                select(ExperienceRow).where(
                    _filter(ExperienceRow, scope),
                    ExperienceRow.fingerprint == candidate.fingerprint,
                )
            )
            if row:
                return await self._expire(session, row)
            if (
                candidate.validation_status != "PROPOSED"
                or candidate.review_status != "UNREVIEWED"
                or candidate.version != 1
                or candidate.expires_at <= self.clock()
            ):
                raise ValueError("New experience must be current, proposed and unreviewed")
            row = ExperienceRow(
                experience_id=candidate.experience_id,
                tenant_ref=scope.tenant_ref,
                user_ref=scope.user_ref,
                session_ref=scope.session_ref,
                fingerprint=candidate.fingerprint,
                version=1,
                payload=candidate.model_dump_json(),
            )
            session.add(row)
            self._event(session, row, "PROPOSED")
            return candidate

    async def get(self, scope, experience_id, *, include_inactive=False):
        scope = _scope(scope)
        async with self.factory() as session, session.begin():
            row = await session.scalar(
                select(ExperienceRow).where(
                    _filter(ExperienceRow, scope), ExperienceRow.experience_id == experience_id
                )
            )
            if not row:
                return None
            value = await self._expire(session, row)
            return (
                value
                if include_inactive or value.validation_status not in {"REJECTED", "EXPIRED"}
                else None
            )

    async def list(self, scope):
        scope = _scope(scope)
        async with self.factory() as session, session.begin():
            rows = (
                await session.scalars(
                    select(ExperienceRow)
                    .where(_filter(ExperienceRow, scope))
                    .order_by(ExperienceRow.experience_id)
                    .limit(256)
                )
            ).all()
            values = [await self._expire(session, row) for row in rows]
            return [v for v in values if v.validation_status not in {"REJECTED", "EXPIRED"}]

    async def transition(
        self, scope, experience_id, status, *, expected_version, validation_evidence=None
    ):
        scope = _scope(scope)
        async with self.factory() as session, session.begin():
            row = await session.scalar(
                select(ExperienceRow).where(
                    _filter(ExperienceRow, scope), ExperienceRow.experience_id == experience_id
                )
            )
            if not row:
                raise ValueError("Experience not found")
            current = await self._expire(session, row)
            allowed = {
                "PROPOSED": {"NEEDS_REVIEW", "REJECTED", "EXPIRED"},
                "NEEDS_REVIEW": {"VERIFIED_OFFLINE", "REJECTED", "EXPIRED"},
                "VERIFIED_OFFLINE": {"REJECTED", "EXPIRED"},
                "REJECTED": set(),
                "EXPIRED": set(),
            }
            if row.version != expected_version or status not in allowed[current.validation_status]:
                raise ValueError("Invalid transition or experience version conflict")
            evidence = ""
            if status == "VERIFIED_OFFLINE":
                if validation_evidence is None:
                    raise ValueError("Independent offline validation evidence required")
                report = self.resolver.resolve(validation_evidence)
                if not isinstance(report, dict) or not all(
                    (
                        report.get("scope") == "offline_applicability",
                        report.get("family") == current.family,
                        report.get("source_version") == current.source_version,
                        report.get("candidate_fingerprint") == current.fingerprint,
                        report.get("independent_labels") is True,
                        report.get("passed") is True,
                        type(report.get("cases")) is int and report["cases"] >= 3,
                        report.get("safety_conflicts") == 0,
                    )
                ):
                    raise ValueError("Independent validation contract not satisfied")
                evidence = validation_evidence.model_dump_json()
            data = current.model_dump() | dict(
                validation_status=status, updated_at=self.clock(), version=current.version + 1
            )
            value = ExperienceCandidate.model_validate(data)
            return await self._write(session, row, value, action=status, evidence_ref=evidence)

    async def review(
        self, scope, experience_id, status, *, expected_version, reviewer_kind="model"
    ):
        scope = _scope(scope)
        if status != "MODEL_REVIEWED" or reviewer_kind != "model":
            raise ValueError("No authenticated human approval channel; never fabricate approval")
        async with self.factory() as session, session.begin():
            row = await session.scalar(
                select(ExperienceRow).where(
                    _filter(ExperienceRow, scope), ExperienceRow.experience_id == experience_id
                )
            )
            if not row:
                raise ValueError("Experience not found")
            current = await self._expire(session, row)
            if row.version != expected_version or current.validation_status in {
                "REJECTED",
                "EXPIRED",
            }:
                raise ValueError("Invalid review or version conflict")
            value = ExperienceCandidate.model_validate(
                current.model_dump()
                | dict(review_status=status, updated_at=self.clock(), version=current.version + 1)
            )
            return await self._write(session, row, value, action=status)

    async def delete(self, scope, experience_id, *, expected_version):
        scope = _scope(scope)
        async with self.factory() as session, session.begin():
            row = await session.scalar(
                select(ExperienceRow).where(
                    _filter(ExperienceRow, scope), ExperienceRow.experience_id == experience_id
                )
            )
            if not row:
                return False
            if row.version != expected_version:
                raise ValueError("Experience version conflict")
            session.add(
                ExperienceTombstoneRow(
                    experience_id=row.experience_id,
                    tenant_ref=scope.tenant_ref,
                    user_ref=scope.user_ref,
                    session_ref=scope.session_ref,
                    fingerprint=row.fingerprint,
                    deleted_at=self.clock().isoformat(),
                )
            )
            await session.execute(
                delete(ExperienceEventRow).where(ExperienceEventRow.experience_id == experience_id)
            )
            await session.delete(row)
            return True
