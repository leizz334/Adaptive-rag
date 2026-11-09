"""Bounded structural evidence; no raw conversations or model reasoning."""

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LocalContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FailureType(StrEnum):
    ROUTING_ERROR = "ROUTING_ERROR"
    QUERY_REWRITE_ERROR = "QUERY_REWRITE_ERROR"
    RETRIEVAL_MISS = "RETRIEVAL_MISS"
    RERANK_ERROR = "RERANK_ERROR"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    MEMORY_RESOLUTION_ERROR = "MEMORY_RESOLUTION_ERROR"
    ENTITY_BINDING_ERROR = "ENTITY_BINDING_ERROR"
    PLANNER_TOOL_SELECTION_ERROR = "PLANNER_TOOL_SELECTION_ERROR"
    PLANNER_ARGUMENT_ERROR = "PLANNER_ARGUMENT_ERROR"
    PLANNER_EXTRA_TOOL = "PLANNER_EXTRA_TOOL"
    PLANNER_MISSING_TOOL = "PLANNER_MISSING_TOOL"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    STALE_BUSINESS_STATE = "STALE_BUSINESS_STATE"
    GOAL_OMISSION = "GOAL_OMISSION"
    ANSWER_FACTUAL_ERROR = "ANSWER_FACTUAL_ERROR"
    ANSWER_FAITHFULNESS_ERROR = "ANSWER_FAITHFULNESS_ERROR"
    JUDGE_INVALID_OUTPUT = "JUDGE_INVALID_OUTPUT"
    JUDGE_API_ERROR = "JUDGE_API_ERROR"
    FALLBACK_ERROR = "FALLBACK_ERROR"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    EVALUATION_CONTRACT_ISSUE = "EVALUATION_CONTRACT_ISSUE"
    UNKNOWN = "UNKNOWN"


class EvidenceRef(LocalContract):
    artifact: str = Field(min_length=1, max_length=512)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    pointer: str = Field(default="", max_length=512)
    kind: Literal["trace", "tool", "document", "evaluation", "request", "configuration"] = "trace"

    @field_validator("artifact")
    @classmethod
    def relative_path(cls, value):
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or ".." in path.parts
            or ":" in value
            or "\\" in value
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError("Relative artifact reference required")
        return value

    @field_validator("pointer")
    @classmethod
    def json_pointer(cls, value):
        if value and not value.startswith("/"):
            raise ValueError("JSON pointer required")
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters forbidden")
        return value


class Proof(StrEnum):
    TRACE_CONTRACT = "TRACE_CONTRACT"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    MODEL_REVIEW = "MODEL_REVIEW"
    SCORE_ONLY = "SCORE_ONLY"
    SCORER_ARTIFACT = "SCORER_ARTIFACT"
    SUCCESS_CONTROL = "SUCCESS_CONTROL"


class FailureSignal(LocalContract):
    category: FailureType
    proof: Proof
    node: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    position: int = Field(ge=0, le=1024)
    evidence_refs: list[EvidenceRef] = Field(max_length=16)
    summary: str = Field(min_length=1, max_length=256)
    root_cause_hypothesis: str = Field(
        default="Mechanism is not uniquely established", max_length=256
    )

    @model_validator(mode="after")
    def references_required(self):
        if (
            self.proof
            in {
                Proof.TRACE_CONTRACT,
                Proof.RUNTIME_ERROR,
                Proof.SCORER_ARTIFACT,
                Proof.MODEL_REVIEW,
            }
            and not self.evidence_refs
        ):
            raise ValueError("Evidence references required")
        return self


class FailureAssessment(LocalContract):
    schema_version: Literal["failure-assessment-v1"] = "failure-assessment-v1"
    source_trace_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    source_case_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    source_version: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    failure_type: FailureType
    evidence_level: Literal[
        "VERIFIED_FAILURE", "LIKELY_FAILURE", "UNDETERMINED", "EVALUATION_ARTIFACT"
    ]
    first_error_node: str | None
    direct_failure: str = Field(max_length=256)
    root_cause_hypothesis: str = Field(max_length=256)
    root_cause_status: Literal["HYPOTHESIS"] = "HYPOTHESIS"
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_source: str
    evidence_refs: list[EvidenceRef] = Field(max_length=64)
    propagation: list[str] = Field(max_length=64)
    alternative_explanations: list[str] = Field(max_length=64)
