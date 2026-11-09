"""Independent synthetic counterexamples; no applicability holdout inputs."""

import hashlib
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.experience.contracts import EvidenceRef, ExperienceScope
from app.experience.reflection import reflect
from app.experience.shadow import EvidenceResolver
from app.experience.storage import ExperienceEventRow, ExperienceRepository, initialize_schema
from app.experience.taxonomy import classify_failure

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def write_ref(path, data, pointer=""):
    path.write_text(json.dumps(data), encoding="utf-8")
    return EvidenceRef(
        artifact=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), pointer=pointer
    )


@pytest.mark.parametrize("data,pointer", [(["first", "last"], "/-1"), ({"~2": "value"}, "/~2")])
def test_resolver_rejects_malformed_json_pointer(tmp_path, data, pointer):
    ref = write_ref(tmp_path / "source.json", data).model_copy(update={"pointer": pointer})
    with pytest.raises(ValueError):
        EvidenceResolver(tmp_path).resolve(ref)


@pytest.fixture
async def review_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'review.sqlite3').as_posix()}")
    await initialize_schema(engine, isolated=True)
    scope = ExperienceScope(
        tenant_ref="a" * 64, user_ref="b" * 64, session_ref="c" * 64, verified=True
    )
    ref = write_ref(tmp_path / "source.json", {})
    assessment = classify_failure(
        source_trace_id="synthetic",
        source_case_id="synthetic",
        source_version="1" * 40,
        signals=[
            dict(
                category="ROUTING_ERROR",
                proof="TRACE_CONTRACT",
                node="router",
                position=1,
                summary="Synthetic verified failure",
                context_tags=["live_fact", "static_policy"],
                evidence_refs=[ref],
            )
        ],
    )
    repo = ExperienceRepository(
        async_sessionmaker(engine, expire_on_commit=False),
        resolver=EvidenceResolver(tmp_path),
        clock=lambda: NOW,
    )
    saved = await repo.propose(scope, reflect(assessment, scope, now=NOW))
    yield repo, engine, scope, saved
    await engine.dispose()


async def test_verification_reference_privacy_matches_source_reference_privacy(
    review_store, tmp_path
):
    repo, engine, scope, saved = review_store
    queued = await repo.transition(scope, saved.experience_id, "NEEDS_REVIEW", expected_version=1)
    # This synthetic email is deliberately a reference name, never source data.
    report = dict(
        scope="offline_applicability",
        family=saved.family,
        source_version=saved.source_version,
        candidate_fingerprint=saved.fingerprint,
        independent_labels=True,
        passed=True,
        cases=3,
        safety_conflicts=0,
    )
    ref = write_ref(tmp_path / "reviewer.person@example.com.json", report).model_copy(
        update={"kind": "evaluation"}
    )
    with pytest.raises(ValueError):
        await repo.transition(
            scope,
            saved.experience_id,
            "VERIFIED_OFFLINE",
            expected_version=queued.version,
            validation_evidence=ref,
        )
    async with async_sessionmaker(engine)() as session:
        events = (await session.scalars(select(ExperienceEventRow))).all()
    assert all("reviewer.person@example.com" not in e.evidence_ref for e in events)


async def test_delete_checks_version_at_actual_delete(review_store):
    repo, engine, scope, saved = review_store
    trigger = [True]

    class ConcurrentSession(AsyncSession):
        async def scalar(self, *args, **kwargs):
            result = await super().scalar(*args, **kwargs)
            if trigger[0]:
                trigger[0] = False
                await repo.transition(
                    scope, saved.experience_id, "NEEDS_REVIEW", expected_version=1
                )
            return result

    repo.factory = async_sessionmaker(engine, class_=ConcurrentSession, expire_on_commit=False)
    with pytest.raises(ValueError, match="version conflict"):
        await repo.delete(scope, saved.experience_id, expected_version=1)
    latest = await repo.get(scope, saved.experience_id)
    assert latest is not None and latest.version == 2
