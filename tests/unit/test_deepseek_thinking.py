"""Modern model JSON compatibility; fake credentials and MockTransport only."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider


@pytest.mark.parametrize("stream", [False, True])
async def test_explicit_non_thinking_mode_reaches_json_and_stream_payloads(stream):
    seen = []

    def respond(request):
        seen.append(json.loads(request.content))
        if stream:
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"hello"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    settings = Settings(
        _env_file=None,
        deepseek_api_key="synthetic-test-only",
        deepseek_model="deepseek-flash",
        deepseek_thinking_mode="disabled",
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.deepseek.com"
    ) as client:
        provider = DeepSeekProvider(settings, client=client)
        if stream:
            assert (
                "".join(
                    [
                        part
                        async for part in provider.stream(
                            [{"role": "user", "content": "hello"}], max_tokens=32
                        )
                    ]
                )
                == "hello"
            )
        else:
            assert (
                await provider.generate([{"role": "user", "content": "hello"}], max_tokens=32)
            ).content == "hello"
    assert seen[0].get("thinking") == {
        "type": "disabled"
    }, "Modern models default to thinking; short structured outputs need explicit control"


def test_invalid_thinking_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, deepseek_thinking_mode="invalid")
