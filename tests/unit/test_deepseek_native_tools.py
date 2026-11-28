import json

import httpx
import pytest

from app.config.settings import Settings
from app.core.exceptions import LLMProviderError
from app.providers.deepseek import DeepSeekProvider

TOOL_CALL = {
    "id": "call_order_1",
    "type": "function",
    "function": {"name": "get_order", "arguments": '{"order_id":"FIXTURE-1"}'},
}

ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
}


async def test_generate_preserves_the_native_tool_exchange_and_synthetic_bodies():
    requests = []
    tool_response = {
        "id": "completion_fixture",
        "model": "reported-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": None, "tool_calls": [TOOL_CALL]},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 23,
            "completion_tokens": 13,
            "total_tokens": 36,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 23,
        },
    }

    def respond(request):
        assert request.url.path == "/beta/chat/completions"
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, json=tool_response)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The order has shipped."}}]},
        )

    messages = [{"role": "user", "content": "Check fixture order."}]
    async with httpx.AsyncClient(
        base_url="https://offline.invalid/beta", transport=httpx.MockTransport(respond)
    ) as client:
        provider = DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="offline-key", deepseek_model="pinned-model"),
            client,
            thinking_enabled=False,
            capture_raw=True,
        )
        result = await provider.generate(messages, tools=[ORDER_TOOL], tool_choice="auto")
        assert result.content == ""
        assert result.tool_calls == [TOOL_CALL]
        assert result.finish_reason == "tool_calls"
        assert result.model == "reported-model"
        assert result.usage.total_tokens == 36
        assert result.prompt_cache_hit_tokens == 0
        assert result.prompt_cache_miss_tokens == 23
        assert result.raw_response == tool_response

        messages.extend(
            [
                {"role": "assistant", "content": None, "tool_calls": result.tool_calls},
                {"role": "tool", "tool_call_id": "call_order_1", "content": '{"status":"shipped"}'},
            ]
        )
        answer = await provider.generate(messages)

    assert requests[0] == {
        "model": "pinned-model",
        "messages": [{"role": "user", "content": "Check fixture order."}],
        "temperature": 0.0,
        "max_tokens": 1024,
        "thinking": {"type": "disabled"},
        "tools": [ORDER_TOOL],
        "tool_choice": "auto",
    }
    assert result.raw_request == requests[0]
    assert requests[1]["messages"] == messages
    assert answer.content == "The order has shipped."
    assert answer.tool_calls == []
    assert answer.prompt_cache_hit_tokens is None
    assert answer.prompt_cache_miss_tokens is None


async def test_generate_keeps_text_completion_defaults_and_raw_capture_opt_in():
    def respond(request):
        assert json.loads(request.content) == {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "Hello."}],
            "temperature": 0.0,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"hi"}'}}]},
        )

    async with httpx.AsyncClient(
        base_url="https://offline.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        provider = DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="offline-key"), client
        )
        result = await provider.generate(
            [{"role": "user", "content": "Hello."}], response_format={"type": "json_object"}
        )

    assert result.content == '{"answer":"hi"}'
    assert result.raw_request is None
    assert result.raw_response is None


async def test_generate_counts_tool_schemas_toward_its_request_budget():
    def respond(request):
        pytest.fail("A request with an oversized tool schema reached HTTP transport")

    async with httpx.AsyncClient(
        base_url="https://offline.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        provider = DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="offline-key", token_budget=500), client
        )
        with pytest.raises(LLMProviderError, match="budget"):
            await provider.generate(
                [{"role": "user", "content": "Hello."}],
                tools=[ORDER_TOOL],
                max_tokens=100,
            )
