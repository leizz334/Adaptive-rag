import json

import pytest
from pydantic import ValidationError

from app.agents.nodes.faithfulness import faithfulness_node
from app.agents.nodes.generate import generate_node
from app.config.settings import Settings
from app.core.enums import RetrievalStrategy
from app.core.exceptions import LLMProviderError
from app.guardrails.hallucination import FaithfulnessChecker
from app.providers.base import LLMResponse
from app.schemas.retrieval import RetrievedChunk


def _state():
    return {
        "user_query": "What is the policy?",
        "strategy": RetrievalStrategy.MULTI,
        "retrieved_chunks": [
            RetrievedChunk(
                chunk_id=f"chunk-{i}",
                document_id="policy",
                title="Policy",
                content=f"Detail {i}",
                score=1.0,
            )
            for i in range(10)
        ],
    }


class _Answerer:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.prompts = []

    async def generate(self, messages, **kwargs):
        self.prompts.append(messages[-1]["content"])
        return LLMResponse(json.dumps(next(self.replies)))


@pytest.mark.parametrize("limit", [None, 1, 4, 8, 20])
async def test_generation_citations_only_reference_the_selected_context(limit, caplog):
    llm = _Answerer({"answer": "Policy", "citation_chunk_ids": ["chunk-0", "chunk-7", "chunk-9"]})
    settings = Settings() if limit is None else Settings(generation_top_n=limit)
    caplog.set_level("INFO")
    selected = min(limit or 6, 10)
    state = _state()
    result = await generate_node(state, llm, settings=settings)
    expected_ids = [f"chunk-{i}" for i in range(selected)]
    assert [chunk.chunk_id for chunk in result["generation_chunks"]] == expected_ids
    assert [citation.chunk_id for citation in result["citations"]] == [
        chunk_id for chunk_id in ["chunk-0", "chunk-7", "chunk-9"] if chunk_id in expected_ids
    ]
    assert all((f"[chunk-{i}]" in llm.prompts[0]) == (i < selected) for i in range(10))
    log = next(record for record in caplog.records if record.msg == "generation_context_selected")
    assert log.chunk_count == selected
    assert log.estimated_context_tokens > 0


@pytest.mark.parametrize("limit", [0, -1, 2.5, "invalid"])
def test_generation_top_n_rejects_invalid_limits(limit):
    with pytest.raises(ValidationError):
        Settings(generation_top_n=limit)


async def test_correction_and_judgment_use_the_same_context_and_refresh_citations():
    llm = _Answerer(
        {"answer": "Initial", "citation_chunk_ids": ["chunk-0"]},
        {"supported": False},
        {"answer": "Corrected", "citation_chunk_ids": ["chunk-8", "chunk-9"]},
        {"supported": True},
    )
    state = _state()
    state.update(await generate_node(state, llm, settings=Settings(generation_top_n=9)))
    state.update(await faithfulness_node(state, FaithfulnessChecker(llm), llm))
    assert state["final_answer"] == "Corrected"
    assert [citation.chunk_id for citation in state["citations"]] == ["chunk-8"]
    assert all("[chunk-8]" in prompt and "[chunk-9]" not in prompt for prompt in llm.prompts)


async def test_empty_selected_context_has_no_citations_or_token_estimate(caplog):
    llm = _Answerer({"answer": "No evidence", "citation_chunk_ids": ["chunk-0"]})
    caplog.set_level("INFO")
    result = await generate_node({"user_query": "What is the policy?"}, llm, settings=Settings())
    assert result["generation_chunks"] == []
    assert result["citations"] == []
    log = next(record for record in caplog.records if record.msg == "generation_context_selected")
    assert log.chunk_count == log.estimated_context_tokens == 0


async def test_extractive_fallback_quotes_only_the_chunk_it_cites():
    class FailingProvider:
        async def generate(self, messages, **kwargs):
            raise LLMProviderError("unavailable")

    result = await generate_node(_state(), FailingProvider(), settings=Settings(generation_top_n=2))
    assert "Detail 0" in result["final_answer"]
    assert "Detail 1" not in result["final_answer"]
    assert [item.chunk_id for item in result["citations"]] == ["chunk-0"]
