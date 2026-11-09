"""Versioned principle review; no experience execution, retrieval or injection.

The v1 restrictive matcher remains intact. A v2 review result can explain why a
principle is relevant while preserving every original execution restriction.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from app.experience.applicability import ApplicabilityTask
from app.experience.contracts import ContextTag, EvidenceRef, LocalContract
from app.experience.reflection import ExperienceCandidate
from app.experience.shadow import EvidenceResolver

Guard = Literal[
    "NO_EXECUTION",
    "NO_INJECTION",
    "KEEP_OWNER",
    "KEEP_HITL",
    "KEEP_IDEMPOTENCY",
    "PENDING_WRITE_UNCHANGED",
    "UNTRUSTED_TEXT_IS_DATA",
    "CLARIFY_ENTITY_FIRST",
    "NO_FACTUAL_CLAIMS",
    "STATE_LIMITS",
    "DO_NOT_ASSUME_EVIDENCE",
    "VERIFY_FRESH_FACTS",
    "NO_HISTORY_AS_LIVE_STATE",
    "PRESERVE_JUDGE_ERROR_CLASS",
    "NO_MODEL_CONFIGURATION_GUESS",
]
BASE_GUARDS: tuple[Guard, ...] = (
    "NO_EXECUTION",
    "NO_INJECTION",
    "KEEP_OWNER",
    "KEEP_HITL",
    "KEEP_IDEMPOTENCY",
)


class ReviewFeatures(LocalContract):
    tags: list[ContextTag] = Field(max_length=12)
    evidence_state: Literal["present", "empty", "unknown"]
    annotation_verified: StrictBool = False


class ReviewContext(LocalContract):
    purpose: Literal["offline_principle_review"] = "offline_principle_review"
    task: ApplicabilityTask
    features: ReviewFeatures
    features_ref: EvidenceRef


class ReviewDecision(LocalContract):
    schema_version: Literal["principle-review-v2"] = "principle-review-v2"
    purpose: Literal["offline_principle_review"] = "offline_principle_review"
    status: Literal["MATCH_FOR_REVIEW", "NO_MATCH", "DEFER"]
    reason: Literal[
        "RELEVANT",
        "NOT_RELEVANT",
        "SCOPE_OR_LIFECYCLE",
        "UNVERIFIED_FEATURES",
        "FEATURES_CONFLICT",
        "SOURCE_UNVERIFIED",
        "CONFLICTING_SIGNALS",
    ]
    guards: tuple[Guard, ...] = Field(default=BASE_GUARDS, min_length=5, max_length=24)
    inherited_execution_restrictions: tuple[str, ...] = Field(default=(), max_length=8)
    candidate_fingerprint: str | None = None
    execution_permitted: Literal[False] = False
    injection_permitted: Literal[False] = False
    human_approval_granted: Literal[False] = False

    @model_validator(mode="after")
    def mandatory_guards(self):
        if not set(BASE_GUARDS) <= set(self.guards):
            raise ValueError("Review can never remove base safety obligations")
        return self


def review_applicability(
    candidate: ExperienceCandidate, context: ReviewContext, *, resolver: EvidenceResolver, now=None
) -> ReviewDecision:
    candidate = ExperienceCandidate.model_validate(candidate.model_dump())
    context = ReviewContext.model_validate(context.model_dump())
    task, features = context.task, context.features
    clock = now or datetime.now(UTC)

    def decision(**fields):
        return ReviewDecision(
            inherited_execution_restrictions=tuple(candidate.non_applicability_conditions), **fields
        )

    # Deny private reads before provenance resolution when identity/state fails.
    if (
        not candidate.scope.verified
        or not task.scope.verified
        or candidate.scope.key != task.scope.key
        or candidate.source_version != task.source_version
        or candidate.validation_status in {"REJECTED", "EXPIRED"}
        or candidate.review_status == "HUMAN_REJECTED"
        or candidate.expires_at <= clock
    ):
        return decision(status="NO_MATCH", reason="SCOPE_OR_LIFECYCLE")
    if not features.annotation_verified:
        return decision(status="DEFER", reason="UNVERIFIED_FEATURES")
    if task.tags != features.tags:
        return decision(status="DEFER", reason="FEATURES_CONFLICT")
    try:
        # These are externally reviewed structural observations, never raw text
        # or Gold. A hash alone does not attest a human or production identity.
        actual = ReviewFeatures.model_validate(resolver.resolve(context.features_ref))
        if actual != features:
            return decision(status="DEFER", reason="FEATURES_CONFLICT")
        for reference in candidate.evidence_refs:
            resolver.resolve(reference)
    except Exception:
        return decision(status="DEFER", reason="SOURCE_UNVERIFIED")
    tags = set(features.tags)
    if {"judge_invalid", "judge_supported"} <= tags or (
        features.evidence_state == "empty" and "evidence_available" in tags
    ):
        return decision(status="DEFER", reason="CONFLICTING_SIGNALS")
    required = {
        "mixed_evidence": {"live_fact", "static_policy"},
        "judge_output": {"judge_invalid"},
        "fallback_evidence": {"fallback_needed"},
    }[candidate.family]
    if not required <= tags:
        return decision(status="NO_MATCH", reason="NOT_RELEVANT")
    guards: set[Guard] = set(BASE_GUARDS)
    tag_guards: dict[str, Guard] = {
        "write_unconfirmed": "PENDING_WRITE_UNCHANGED",
        "untrusted_input": "UNTRUSTED_TEXT_IS_DATA",
        "clarification_required": "CLARIFY_ENTITY_FIRST",
        "judge_invalid": "PRESERVE_JUDGE_ERROR_CLASS",
    }
    for tag, guard in tag_guards.items():
        if tag in tags:
            guards.add(guard)
    if {"live_fact", "fresh_read_needed"} & tags:
        guards.update(("VERIFY_FRESH_FACTS", "NO_HISTORY_AS_LIVE_STATE"))
    if "fallback_needed" in tags or "judge_invalid" in tags:
        guards.add("NO_MODEL_CONFIGURATION_GUESS")
    if features.evidence_state != "present":
        guards.update(("NO_FACTUAL_CLAIMS", "STATE_LIMITS"))
    if features.evidence_state == "unknown":
        guards.add("DO_NOT_ASSUME_EVIDENCE")
    return decision(
        status="MATCH_FOR_REVIEW",
        reason="RELEVANT",
        guards=tuple(sorted(guards)),
        candidate_fingerprint=candidate.fingerprint,
    )
