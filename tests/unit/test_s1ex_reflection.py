from datetime import UTC, datetime

import pytest

from app.experience.contracts import EvidenceRef, ExperienceScope, FailureAssessment, FailureType
from app.experience.reflection import reflect


@pytest.mark.parametrize(
    "failure,tags,family",
    [
        ("PLANNER_MISSING_TOOL", ["live_fact", "multi_goal"], "tool_coverage"),
        ("PLANNER_ARGUMENT_ERROR", ["live_fact", "plan_contract"], "plan_contract"),
        ("GOAL_OMISSION", ["live_fact", "multi_goal", "evidence_available"], "answer_coverage"),
    ],
)
def test_verified_structural_failure_reflects_safe_principle(failure, tags, family):
    scope = ExperienceScope(
        tenant_ref="a" * 64, user_ref="b" * 64, session_ref="c" * 64, verified=True
    )
    assessment = FailureAssessment(
        source_trace_id="synthetic_trace",
        source_case_id="synthetic_case",
        source_version="d" * 40,
        failure_type=FailureType(failure),
        evidence_level="VERIFIED_FAILURE",
        first_error_node="planner",
        direct_failure="bounded verified structural divergence",
        root_cause_hypothesis="not uniquely known",
        confidence="HIGH",
        confidence_source="TRACE_CONTRACT",
        evidence_refs=[EvidenceRef(artifact="evidence/opaque.json", sha256="e" * 64)],
        propagation=[],
        alternative_explanations=[],
        context_tags=tags,
    )
    value = reflect(assessment, scope, now=datetime(2026, 11, 12, tzinfo=UTC))
    assert value is not None and value.family == family
    assert value.review_status == "UNREVIEWED" and value.validation_status == "PROPOSED"


def test_compatibility_never_approves_and_changed_contract_denies():
    from app.experience.compatibility import check_compatibility

    manifest = {"tools": {"read": "a"}, "features": {"owner": "b"}}
    yes = check_compatibility(manifest, dict(manifest), tools=["read"], features=["owner"])
    assert yes["compatible"] and not yes["approval_granted"]
    assert not check_compatibility(
        manifest,
        {"tools": {"read": "changed"}, "features": {"owner": "b"}},
        tools=["read"],
        features=["owner"],
    )["compatible"]
    assert not check_compatibility(manifest, manifest, tools=[], features=[])["compatible"]
