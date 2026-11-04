import httpx
import pytest

from app.config.settings import Settings
from app.core.exceptions import LLMProviderError
from app.providers.deepseek import DeepSeekProvider
from app.schemas.chat import ChatMessage


async def test_complete_serialized_input_and_output_reservation_checked_before_http():
    calls = []
    async with httpx.AsyncClient(
        base_url="https://offline.invalid",
        transport=httpx.MockTransport(
            lambda r: calls.append(r)
            or httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        ),
    ) as client:
        provider = DeepSeekProvider(
            Settings(_env_file=None, deepseek_api_key="OFFLINE", token_budget=900), client
        )
        with pytest.raises(LLMProviderError, match="budget"):
            await provider.generate(
                [
                    {"role": "system", "content": "system schema"},
                    {"role": "user", "content": "工具结果/检索证据" * 1000},
                ],
                max_tokens=500,
                response_format={"type": "json_object"},
            )
    assert not calls


def test_selected_memory_payload_bounded_without_truncating_entity():
    from app.memory.context import ContextBuilder

    selected = ContextBuilder(
        Settings(_env_file=None, memory_mode="M2", memory_context_max_chars=256)
    ).build(
        "它现在是什么状态",
        [ChatMessage(role="user", content="很长的历史" * 500 + " ORD10001")],
        summary="旧摘要" * 1000,
    )
    text = selected.prompt_context("generate")
    assert len(text) <= 256 and "ORD10001" in text
