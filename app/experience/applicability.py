"""Offline candidate matching only; no Agent recall, injection or activation API."""

from datetime import UTC, datetime

from pydantic import Field

from app.experience.contracts import ContextTag, ExperienceScope, LocalContract
from app.experience.reflection import ExperienceCandidate


class ApplicabilityTask(LocalContract):
    scope: ExperienceScope
    tags: list[ContextTag] = Field(max_length=12)
    source_version: str = Field(pattern=r"^[a-f0-9]{40,64}$")


def matches_offline(candidate: ExperienceCandidate, task: ApplicabilityTask, *, now=None) -> bool:
    candidate = ExperienceCandidate.model_validate(candidate.model_dump())
    task = ApplicabilityTask.model_validate(task.model_dump())
    clock = now or datetime.now(UTC)
    if (
        not candidate.scope.verified
        or not task.scope.verified
        or candidate.scope.key != task.scope.key
    ):
        return False
    if (
        candidate.source_version != task.source_version
        or candidate.validation_status in {"REJECTED", "EXPIRED"}
        or candidate.review_status == "HUMAN_REJECTED"
        or candidate.expires_at <= clock
    ):
        return False
    tags = set(task.tags)
    return (
        set(candidate.applicability_conditions) <= tags
        and not set(candidate.non_applicability_conditions) & tags
    )
