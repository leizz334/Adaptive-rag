"""Bounded reflection catalog, not autonomous learning or production approval."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict
from uuid import uuid4

from pydantic import Field, model_validator

from app.experience.contracts import (
    EvidenceRef,
    ExperienceScope,
    FailureAssessment,
    FailureType,
    LocalContract,
)

Family = Literal["mixed_evidence", "judge_output", "fallback_evidence"]


class LessonTemplate(TypedDict):
    lesson: str
    required: list[str]
    excluded: list[str]


CATALOG: dict[Family, LessonTemplate] = {
    "mixed_evidence": dict(
        lesson="请求同时包含实时业务事实和静态政策时，分别核对两类所需证据；静态检索不能替代实时业务读取。保留权限、Owner、人工确认与幂等检查，证据不足时明确说明限制。",
        required=["live_fact", "static_policy"],
        excluded=["untrusted_input", "clarification_required"],
    ),
    "judge_output": dict(
        lesson="结构化裁判输出非法或截断时，保留真实错误类别；不能据此认定原回答正确或有幻觉。只陈述已经验证的证据与未确认限制，不推断模型配置，也不声称未经确认的操作成功。",
        required=["judge_invalid", "evidence_available"],
        excluded=["untrusted_input", "write_unconfirmed"],
    ),
    "fallback_evidence": dict(
        lesson="生成或回退失败时，仅基于成功且完整的工具或文档证据组织事实与限制；不得把无关资料当作答案，不得编造模型配置原因或已完成的业务操作。",
        required=["fallback_needed", "evidence_available"],
        excluded=["untrusted_input", "write_unconfirmed"],
    ),
}
HYPOTHESIS = "Observed failure supports a candidate principle; the internal root cause is not uniquely established."


class ExperienceCandidate(LocalContract):
    experience_id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-f0-9]{32}$")
    schema_version: Literal["experience-shadow-v1"] = "experience-shadow-v1"
    scope: ExperienceScope
    source_trace_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    source_case_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    failure_type: FailureType
    failure_confidence: Literal["HIGH"] = "HIGH"
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=64)
    root_cause_hypothesis: str = HYPOTHESIS
    family: Family
    lesson: str = Field(max_length=1024)
    applicability_conditions: list[str] = Field(max_length=8)
    non_applicability_conditions: list[str] = Field(max_length=8)
    risk_level: Literal["LOW"] = "LOW"
    validation_status: Literal[
        "PROPOSED", "NEEDS_REVIEW", "VERIFIED_OFFLINE", "REJECTED", "EXPIRED"
    ] = "PROPOSED"
    review_status: Literal["UNREVIEWED", "MODEL_REVIEWED", "HUMAN_APPROVED", "HUMAN_REJECTED"] = (
        "UNREVIEWED"
    )
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    source_version: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def catalog_and_time(self):
        template = CATALOG[self.family]
        if (
            self.lesson != template["lesson"]
            or self.applicability_conditions != template["required"]
            or self.non_applicability_conditions != template["excluded"]
            or self.root_cause_hypothesis != HYPOTHESIS
        ):
            raise ValueError("Only reviewed generic catalog text may enter this shadow prototype")
        if any(
            t.tzinfo is None or t.utcoffset() != timedelta(0)
            for t in (self.created_at, self.updated_at, self.expires_at)
        ):
            raise ValueError("UTC-aware timestamps required")
        if (
            not self.created_at <= self.updated_at
            or not self.created_at < self.expires_at
            or (self.validation_status != "EXPIRED" and self.updated_at >= self.expires_at)
            or self.expires_at - self.created_at > timedelta(days=30)
        ):
            raise ValueError("Bounded ordered expiry required")
        return self

    @property
    def fingerprint(self):
        value = dict(
            schema=self.schema_version,
            family=self.family,
            lesson=self.lesson,
            conditions=self.applicability_conditions,
            excluded=self.non_applicability_conditions,
            source_version=self.source_version,
        )
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


def reflect(assessment: FailureAssessment, scope: ExperienceScope, *, now=None):
    scope = ExperienceScope.model_validate(scope.model_dump())
    scope.require_verified()
    assessment = FailureAssessment.model_validate(assessment.model_dump())
    if assessment.evidence_level != "VERIFIED_FAILURE" or not assessment.evidence_refs:
        return None
    families: dict[FailureType, Family] = {
        FailureType.ROUTING_ERROR: "mixed_evidence",
        FailureType.JUDGE_INVALID_OUTPUT: "judge_output",
        FailureType.JUDGE_API_ERROR: "judge_output",
        FailureType.FALLBACK_ERROR: "fallback_evidence",
    }
    family = families.get(assessment.failure_type)
    if family is None:
        return None
    template = CATALOG[family]
    if not set(template["required"]) <= set(assessment.context_tags) or set(
        template["excluded"]
    ) & set(assessment.context_tags):
        return None
    clock = now or datetime.now(UTC)
    return ExperienceCandidate(
        scope=scope,
        source_trace_id=assessment.source_trace_id,
        source_case_id=assessment.source_case_id,
        failure_type=assessment.failure_type,
        evidence_refs=assessment.evidence_refs,
        family=family,
        lesson=template["lesson"],
        applicability_conditions=template["required"],
        non_applicability_conditions=template["excluded"],
        created_at=clock,
        updated_at=clock,
        expires_at=clock + timedelta(days=7),
        source_version=assessment.source_version,
    )
