"""Independent synthetic B0 contract checks; no experiment data or Gold reads."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.experience.applicability import ApplicabilityTask
from app.experience.contracts import EvidenceRef, ExperienceScope
from app.experience.reflection import CATALOG, ExperienceCandidate
from app.experience.review_applicability import ReviewContext, review_applicability
from app.experience.shadow import EvidenceResolver

NOW = datetime(2026, 11, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    "tags,verified,status",
    [
        (["live_fact", "static_policy", "untrusted_input"], True, "MATCH_FOR_REVIEW"),
        (["live_fact"], True, "NO_MATCH"),
        (["live_fact", "static_policy"], False, "DEFER"),
    ],
)
def test_every_review_result_preserves_original_execution_restrictions(
    tmp_path, tags, verified, status
):
    scope = ExperienceScope(
        tenant_ref="1" * 64, user_ref="2" * 64, session_ref="3" * 64, verified=True
    )
    features = dict(tags=tags, evidence_state="present", annotation_verified=verified)
    payload = tmp_path / "synthetic.json"
    payload.write_text(json.dumps(features), encoding="utf-8")
    reference = EvidenceRef(
        artifact=payload.name, sha256=hashlib.sha256(payload.read_bytes()).hexdigest()
    )
    template = CATALOG["mixed_evidence"]
    candidate = ExperienceCandidate(
        scope=scope,
        source_trace_id="synthetic-trace",
        source_case_id="synthetic-case",
        failure_type="ROUTING_ERROR",
        evidence_refs=[reference],
        family="mixed_evidence",
        lesson=template["lesson"],
        applicability_conditions=template["required"],
        non_applicability_conditions=template["excluded"],
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW + timedelta(days=1),
        source_version="a" * 40,
    )
    context = ReviewContext(
        task=ApplicabilityTask(scope=scope, tags=tags, source_version="a" * 40),
        features=features,
        features_ref=reference,
    )
    result = review_applicability(candidate, context, resolver=EvidenceResolver(tmp_path), now=NOW)
    assert result.status == status
    assert result.execution_permitted is False
    assert result.injection_permitted is False
    assert result.human_approval_granted is False
    assert result.inherited_execution_restrictions == tuple(candidate.non_applicability_conditions)
