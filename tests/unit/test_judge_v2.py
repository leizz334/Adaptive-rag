import pytest

from app.core.exceptions import LLMProviderError
from app.guardrails.hallucination import FaithfulnessChecker, FaithfulnessResult
from app.providers.base import LLMResponse
from app.schemas.retrieval import RetrievedChunk
from eval.judge_metrics import paired_hallucination_drop, summarize_judgments


class Judge:
    def __init__(self, output=None, error=False):
        self.output = output
        self.error = error

    async def generate(self, *args, **kwargs):
        if self.error:
            raise LLMProviderError("synthetic private failure")
        return LLMResponse(self.output)


@pytest.mark.parametrize(
    "output,status",
    [
        ('{"supported": true}', "SUPPORTED"),
        ('{"supported": false}', "UNSUPPORTED"),
        ('{"status": "INSUFFICIENT_EVIDENCE"}', "INSUFFICIENT_EVIDENCE"),
        ("not-json", "INVALID_OUTPUT"),
        ('{"something": true}', "INVALID_OUTPUT"),
        ('{"supported": "yes"}', "INVALID_OUTPUT"),
        ('{"status": "SUPPORTED", "supported": false}', "INVALID_OUTPUT"),
    ],
)
async def test_judge_statuses_and_legacy_bool(output, status):
    checker = FaithfulnessChecker(Judge(output))
    result = await checker.check(
        query="q",
        answer="a",
        chunks=[
            RetrievedChunk(chunk_id="c", document_id="d", title="t", content="policy", score=1.0)
        ],
        tool_results_text="",
    )
    assert result.status.value == status
    assert result.supported == (status == "SUPPORTED")


async def test_provider_error_and_no_evidence_not_hallucinations():
    checker = FaithfulnessChecker(Judge(error=True))
    error = await checker.check(
        query="q", answer="a", chunks=[], tool_results_text='{"observed": 1}'
    )
    empty = await checker.check(query="q", answer="a", chunks=[], tool_results_text="[]")
    assert error.status.value == "JUDGE_ERROR"
    assert empty.status.value == "INSUFFICIENT_EVIDENCE"
    summary = summarize_judgments(
        [error, empty, FaithfulnessResult(supported=True), FaithfulnessResult(supported=False)]
    )
    assert summary["hallucination_rate"] == 0.5
    assert summary["judged_coverage"] == 0.5
    assert summary["status_counts"]["JUDGE_ERROR"] == 1
    assert summarize_judgments([error])["hallucination_rate"] is None


async def test_judge_outage_not_counted_in_hallucination_metric():
    from app.agents.nodes.faithfulness import faithfulness_node
    from app.core.enums import RetrievalStrategy
    from app.observability.metrics import HALLUCINATION_FLAGS

    before = HALLUCINATION_FLAGS._value.get()
    await faithfulness_node(
        {
            "user_query": "q",
            "final_answer": "a",
            "strategy": RetrievalStrategy.SINGLE,
            "retrieved_chunks": [
                RetrievedChunk(
                    chunk_id="c", document_id="d", title="t", content="policy", score=1.0
                )
            ],
        },
        FaithfulnessChecker(Judge(error=True)),
        Judge(error=True),
    )
    assert HALLUCINATION_FLAGS._value.get() == before


def test_equal_coverage_of_different_cases_does_not_claim_improvement():
    bad = FaithfulnessResult(supported=False)
    good = FaithfulnessResult(supported=True)
    error = FaithfulnessResult(status="JUDGE_ERROR")
    assert paired_hallucination_drop([bad, error], [error, good]) is None
    assert paired_hallucination_drop([bad, good], [good, good]) == 1.0
