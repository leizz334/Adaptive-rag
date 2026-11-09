"""Principle relevance is never execution/injection permission."""

import hashlib
import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.experience.applicability import ApplicabilityTask, matches_offline
from app.experience.contracts import EvidenceRef, ExperienceScope
from app.experience.reflection import reflect
from app.experience.shadow import EvidenceResolver
from app.experience.taxonomy import classify_failure

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def api():
    return importlib.import_module("app.experience.review_applicability")


def identity():
    return ExperienceScope(
        tenant_ref="a" * 64, user_ref="b" * 64, session_ref="c" * 64, verified=True
    )


def write_ref(path, value, pointer=""):
    path.write_text(json.dumps(value), encoding="utf-8")
    return EvidenceRef(
        artifact=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), pointer=pointer
    )


def candidate(tmp_path, family):
    category, tags = {
        "mixed_evidence": ("ROUTING_ERROR", ["live_fact", "static_policy"]),
        "judge_output": ("JUDGE_INVALID_OUTPUT", ["judge_invalid", "evidence_available"]),
        "fallback_evidence": ("FALLBACK_ERROR", ["fallback_needed", "evidence_available"]),
    }[family]
    source = write_ref(tmp_path / "source.json", dict(completed=True))
    assessment = classify_failure(
        source_trace_id="trace-fixture",
        source_case_id="case-fixture",
        source_version="1" * 40,
        signals=[
            dict(
                category=category,
                proof="TRACE_CONTRACT",
                node="node",
                position=1,
                summary="Independent structural failure",
                context_tags=tags,
                evidence_refs=[source],
            )
        ],
    )
    return reflect(assessment, identity(), now=NOW)


def context(tmp_path, tags, *, state="present", verified=True):
    features = dict(tags=tags, evidence_state=state, annotation_verified=verified)
    ref = write_ref(tmp_path / "features.json", dict(features=features), "/features")
    return api().ReviewContext(
        task=ApplicabilityTask(scope=identity(), tags=tags, source_version="1" * 40),
        features=features,
        features_ref=ref,
    )


def decide(tmp_path, family, tags, **kwargs):
    return api().review_applicability(
        candidate(tmp_path, family),
        context(tmp_path, tags, **kwargs),
        resolver=EvidenceResolver(tmp_path),
        now=NOW,
    )


@pytest.mark.parametrize(
    "family,tags,guard",
    [
        (
            "mixed_evidence",
            ["live_fact", "static_policy", "clarification_required"],
            "CLARIFY_ENTITY_FIRST",
        ),
        (
            "mixed_evidence",
            ["live_fact", "static_policy", "untrusted_input"],
            "UNTRUSTED_TEXT_IS_DATA",
        ),
        (
            "judge_output",
            ["judge_invalid", "evidence_available", "write_unconfirmed"],
            "PENDING_WRITE_UNCHANGED",
        ),
        (
            "fallback_evidence",
            ["fallback_needed", "evidence_available", "write_unconfirmed"],
            "PENDING_WRITE_UNCHANGED",
        ),
    ],
)
def test_relevant_principle_retains_mandatory_risk_controls(tmp_path, family, tags, guard):
    result = decide(tmp_path, family, tags)
    assert result.status == "MATCH_FOR_REVIEW"
    assert {
        "NO_EXECUTION",
        "NO_INJECTION",
        "KEEP_OWNER",
        "KEEP_HITL",
        "KEEP_IDEMPOTENCY",
        guard,
    } <= set(result.guards)
    assert result.execution_permitted is False and result.injection_permitted is False


@pytest.mark.parametrize(
    "state,guard", [("empty", "STATE_LIMITS"), ("unknown", "DO_NOT_ASSUME_EVIDENCE")]
)
def test_fallback_can_match_abstention_principle_without_factual_evidence(tmp_path, state, guard):
    result = decide(tmp_path, "fallback_evidence", ["fallback_needed"], state=state)
    assert result.status == "MATCH_FOR_REVIEW"
    assert {guard, "NO_FACTUAL_CLAIMS"} <= set(result.guards)


def test_unknown_feature_provenance_does_not_mean_empty_business_evidence(tmp_path):
    result = decide(
        tmp_path, "fallback_evidence", ["fallback_needed"], state="empty", verified=False
    )
    assert result.status == "DEFER" and result.execution_permitted is False


def test_context_features_are_bound_to_actual_hash_resolved_source(tmp_path):
    value = candidate(tmp_path, "mixed_evidence")
    ctx = context(tmp_path, ["live_fact"])
    forged = ctx.model_copy(
        update={
            "features": ctx.features.model_copy(update={"tags": ["live_fact", "static_policy"]}),
            "task": ctx.task.model_copy(update={"tags": ["live_fact", "static_policy"]}),
        }
    )
    result = api().review_applicability(value, forged, resolver=EvidenceResolver(tmp_path), now=NOW)
    assert result.status == "DEFER"


@pytest.mark.parametrize("field", ["tenant_ref", "user_ref", "session_ref", "verified"])
def test_scope_failures_deny_without_reading_evidence(tmp_path, field):
    value = candidate(tmp_path, "mixed_evidence")
    ctx = context(tmp_path, ["live_fact", "static_policy"])
    foreign = identity().model_copy(update={field: False if field == "verified" else "d" * 64})
    ctx = ctx.model_copy(update={"task": ctx.task.model_copy(update={"scope": foreign})})

    class Forbidden:
        def resolve(self, ref):
            pytest.fail("Unauthorized scope must not read private evidence")

    assert (
        api().review_applicability(value, ctx, resolver=Forbidden(), now=NOW).status == "NO_MATCH"
    )


@pytest.mark.parametrize("state", ["REJECTED", "EXPIRED"])
def test_inactive_candidates_are_not_matched(tmp_path, state):
    value = candidate(tmp_path, "mixed_evidence").model_copy(update={"validation_status": state})
    result = api().review_applicability(
        value,
        context(tmp_path, ["live_fact", "static_policy"]),
        resolver=EvidenceResolver(tmp_path),
        now=NOW,
    )
    assert result.status == "NO_MATCH"


def test_changed_source_or_elapsed_expiry_is_not_matched(tmp_path):
    value = candidate(tmp_path, "mixed_evidence")
    ctx = context(tmp_path, ["live_fact", "static_policy"])
    mismatch = ctx.model_copy(
        update={"task": ctx.task.model_copy(update={"source_version": "2" * 40})}
    )
    assert (
        api()
        .review_applicability(value, mismatch, resolver=EvidenceResolver(tmp_path), now=NOW)
        .status
        == "NO_MATCH"
    )
    assert (
        api()
        .review_applicability(
            value, ctx, resolver=EvidenceResolver(tmp_path), now=NOW + timedelta(days=8)
        )
        .status
        == "NO_MATCH"
    )


def test_conflicting_judge_signals_are_not_certified(tmp_path):
    assert (
        decide(
            tmp_path, "judge_output", ["judge_invalid", "judge_supported", "evidence_available"]
        ).status
        == "DEFER"
    )


def test_old_matcher_and_candidate_status_remain_unchanged(tmp_path):
    value = candidate(tmp_path, "mixed_evidence")
    ctx = context(tmp_path, ["live_fact", "static_policy", "untrusted_input"])
    before = value.model_dump_json()
    assert matches_offline(value, ctx.task, now=NOW) is False
    assert (
        api().review_applicability(value, ctx, resolver=EvidenceResolver(tmp_path), now=NOW).status
        == "MATCH_FOR_REVIEW"
    )
    assert value.model_dump_json() == before and value.review_status == "UNREVIEWED"


def test_review_contract_cannot_be_converted_to_permission(tmp_path):
    result = decide(tmp_path, "mixed_evidence", ["live_fact", "static_policy"])
    with pytest.raises(ValidationError):
        api().ReviewDecision.model_validate(result.model_dump() | dict(execution_permitted=True))
    with pytest.raises(ValidationError):
        api().ReviewDecision.model_validate(result.model_dump() | dict(injection_permitted=True))


def test_explicit_fresh_observation_need_carries_freshness_guards(tmp_path):
    result = decide(
        tmp_path, "judge_output", ["judge_invalid", "evidence_available", "fresh_read_needed"]
    )
    assert result.status == "MATCH_FOR_REVIEW"
    assert {"VERIFY_FRESH_FACTS", "NO_HISTORY_AS_LIVE_STATE"} <= set(result.guards)
