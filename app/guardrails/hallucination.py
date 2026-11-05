"""Faithfulness scoring against retrieved evidence."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, StrictBool, ValidationError, model_validator

from app.core.exceptions import LLMOutputError, LLMTruncationError
from app.prompts.faithfulness import FAITHFULNESS_SYSTEM, FAITHFULNESS_USER
from app.providers.base import LLMProvider
from app.providers.json_parser import extract_json_object
from app.schemas.retrieval import RetrievedChunk


class FaithfulnessStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    JUDGE_ERROR = "JUDGE_ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class FaithfulnessResult(BaseModel):
    status: FaithfulnessStatus
    supported: StrictBool
    hallucinated_spans: list[str] = Field(default_factory=list, max_length=3)
    rationale: str = Field(default="", max_length=160)
    error_kind: str | None = None

    @model_validator(mode="before")
    @classmethod
    def compatible_verdict(cls, data):
        data = dict(data)
        if "status" not in data:
            if type(data.get("supported")) is not bool:
                raise ValueError("Expected verdict or strict legacy supported boolean")
            data["status"] = "SUPPORTED" if data["supported"] else "UNSUPPORTED"
        status = FaithfulnessStatus(data["status"])
        supported = status == FaithfulnessStatus.SUPPORTED
        if "supported" in data and (
            type(data["supported"]) is not bool or data["supported"] != supported
        ):
            raise ValueError("Contradictory verdict")
        data["supported"] = supported
        return data


class FaithfulnessChecker:
    def __init__(self, llm: LLMProvider, *, max_tokens: int = 512) -> None:
        self._llm = llm
        self._max_tokens = max_tokens

    async def check(
        self,
        *,
        query: str,
        answer: str,
        chunks: list[RetrievedChunk],
        tool_results_text: str,
    ) -> FaithfulnessResult:
        if not chunks and tool_results_text.strip() in {"", "[]", "{}", "(none)", "(无)"}:
            return FaithfulnessResult(
                status=FaithfulnessStatus.INSUFFICIENT_EVIDENCE,
                supported=False,
                rationale="no_evidence",
            )
        evidence = "\n".join(f"[{c.chunk_id}] {c.content}" for c in chunks[:8]) or "(none)"
        try:
            response = await self._llm.generate(
                [
                    {"role": "system", "content": FAITHFULNESS_SYSTEM},
                    {
                        "role": "user",
                        "content": FAITHFULNESS_USER.format(
                            query=query,
                            answer=answer,
                            evidence=evidence,
                            tool_results=tool_results_text or "(none)",
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
            if response.finish_reason == "length":
                raise LLMTruncationError()
        except LLMTruncationError:
            return FaithfulnessResult(
                status=FaithfulnessStatus.INVALID_OUTPUT,
                supported=False,
                rationale="judge_output_truncated",
                error_kind="TRUNCATED",
            )
        except LLMOutputError:
            return FaithfulnessResult(
                status=FaithfulnessStatus.INVALID_OUTPUT,
                supported=False,
                rationale="invalid_or_truncated_judge_output",
                error_kind="INVALID_OUTPUT",
            )
        except Exception:
            return FaithfulnessResult(
                status=FaithfulnessStatus.JUDGE_ERROR,
                supported=False,
                rationale="checker_unavailable",
                error_kind="API_ERROR",
            )
        try:
            payload = extract_json_object(response.content)
        except (LLMOutputError, ValueError, TypeError, AttributeError):
            return FaithfulnessResult(
                status=FaithfulnessStatus.INVALID_OUTPUT,
                supported=False,
                rationale="invalid_judge_json",
                error_kind="MALFORMED_JSON",
            )
        try:
            result = FaithfulnessResult.model_validate(payload)
            if result.status in {FaithfulnessStatus.JUDGE_ERROR, FaithfulnessStatus.INVALID_OUTPUT}:
                raise ValueError("Model cannot declare infrastructure verdict")
            return result
        except (ValidationError, ValueError, TypeError, AttributeError):
            return FaithfulnessResult(
                status=FaithfulnessStatus.INVALID_OUTPUT,
                supported=False,
                rationale="invalid_judge_output",
                error_kind="SCHEMA_ERROR",
            )
