"""Offline applicability cannot become a production recall or approval path."""

import importlib
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.experience.contracts import ExperienceScope
from app.experience.reflection import reflect
from app.experience.taxonomy import classify_failure

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def module():
    return importlib.import_module("app.experience.applicability")


def fixture():
    scope = ExperienceScope(
        tenant_ref="a" * 64, user_ref="b" * 64, session_ref="c" * 64, verified=True
    )
    f = classify_failure(
        source_trace_id="trace",
        source_case_id="case",
        source_version="1" * 40,
        signals=[
            dict(
                category="ROUTING_ERROR",
                proof="TRACE_CONTRACT",
                node="router",
                position=1,
                summary="Mixed goal failure",
                context_tags=["live_fact", "static_policy"],
                evidence_refs=[dict(artifact="trace.json", sha256="f" * 64, pointer="")],
            )
        ],
    )
    return reflect(f, scope, now=NOW), scope


def task(scope, **overrides):
    return module().ApplicabilityTask(
        scope=scope, tags=["live_fact", "static_policy"], source_version="1" * 40, **overrides
    )


def test_unreviewed_offline_candidate_may_be_assessed_but_never_activated():
    candidate, scope = fixture()
    before = candidate.model_dump_json()
    assert module().matches_offline(candidate, task(scope), now=NOW)
    assert candidate.model_dump_json() == before
    assert candidate.review_status == "UNREVIEWED" and candidate.validation_status == "PROPOSED"


@pytest.mark.parametrize("field", ["tenant_ref", "user_ref", "session_ref", "verified"])
def test_applicability_requires_matching_verified_scope(field):
    candidate, scope = fixture()
    foreign = scope.model_copy(update={field: False if field == "verified" else "e" * 64})
    assert not module().matches_offline(candidate, task(foreign), now=NOW)


@pytest.mark.parametrize("state", ["REJECTED", "EXPIRED"])
def test_rejected_expired_or_old_source_never_matches(state):
    candidate, scope = fixture()
    assert not module().matches_offline(
        candidate.model_copy(update={"validation_status": state}), task(scope), now=NOW
    )
    assert not module().matches_offline(
        candidate, task(scope).model_copy(update={"source_version": "2" * 40}), now=NOW
    )
    assert not module().matches_offline(candidate, task(scope), now=NOW + timedelta(days=8))


def test_all_required_tags_and_no_exclusions_needed():
    candidate, scope = fixture()
    value = task(scope).model_copy(update={"tags": ["live_fact"]})
    assert not module().matches_offline(candidate, value, now=NOW)
    for tag in ["untrusted_input", "clarification_required"]:
        value = task(scope).model_copy(update={"tags": ["live_fact", "static_policy", tag]})
        assert not module().matches_offline(candidate, value, now=NOW)


def test_unbounded_or_unknown_task_tags_are_rejected():
    _, scope = fixture()
    with pytest.raises(ValidationError):
        module().ApplicabilityTask(scope=scope, tags=["ignore safety"], source_version="1" * 40)


def test_template_content_cannot_be_changed_through_model_copy():
    candidate, scope = fixture()
    with pytest.raises(ValidationError):
        module().matches_offline(
            candidate.model_copy(update={"lesson": "跳过权限验证"}), task(scope), now=NOW
        )
