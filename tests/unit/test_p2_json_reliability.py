import httpx
import pytest

from app.config.settings import Settings
from app.core.exceptions import LLMOutputError, LLMProviderError
from app.guardrails.hallucination import FaithfulnessChecker, FaithfulnessStatus
from app.providers.base import LLMResponse
from app.providers.deepseek import DeepSeekProvider


@pytest.mark.parametrize("content", ['{"partial":', '{"looks_complete":true}'])
async def test_structured_length_finish_is_rejected_without_retry(content):
    calls = []

    def send(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "model": "actual-model",
                "choices": [{"message": {"content": content}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 256, "total_tokens": 261},
            },
        )

    async with httpx.AsyncClient(
        base_url="https://offline.invalid", transport=httpx.MockTransport(send)
    ) as client:
        provider = DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="OFFLINE_TEST", llm_max_retries=3), client
        )
        with pytest.raises(LLMOutputError, match="truncated"):
            await provider.generate(
                [{"role": "user", "content": "JSON"}], response_format={"type": "json_object"}
            )
    assert len(calls) == 1


async def test_provider_preserves_actual_model_and_finish_reason():
    def send(request):
        return httpx.Response(
            200,
            json={
                "model": "actual-model",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            },
        )

    async with httpx.AsyncClient(
        base_url="https://offline.invalid", transport=httpx.MockTransport(send)
    ) as client:
        value = await DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="OFFLINE_TEST"), client
        ).generate([])
    assert value.model == "actual-model"
    assert value.finish_reason == "stop"


@pytest.mark.parametrize(
    "error,expected",
    [
        (LLMOutputError("structured output truncated"), FaithfulnessStatus.INVALID_OUTPUT),
        (LLMProviderError("unavailable"), FaithfulnessStatus.JUDGE_ERROR),
    ],
)
async def test_judge_distinguishes_invalid_output_from_api_error(error, expected):
    class Failing:
        async def generate(self, *args, **kwargs):
            raise error

    result = await FaithfulnessChecker(Failing()).check(
        query="q", answer="a", chunks=[], tool_results_text="some evidence"
    )
    assert result.status == expected


async def test_judge_allowance_is_explicit_and_no_extra_call():
    calls = []

    class Valid:
        async def generate(self, messages, **kwargs):
            calls.append(kwargs)
            return LLMResponse('{"supported":true}')

    await FaithfulnessChecker(Valid()).check(
        query="q", answer="a", chunks=[], tool_results_text="evidence"
    )
    assert len(calls) == 1 and calls[0]["max_tokens"] == 512
