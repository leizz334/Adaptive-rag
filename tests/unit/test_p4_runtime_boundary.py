import importlib
import json

import pytest


def api():
    return importlib.import_module("research.docs.agent_engineering_upgrade.p4_api_e2e.worker")


def test_only_loopback_socket_connections_are_allowed_for_windows_asyncio():
    assert api().loopback_address(("127.0.0.1", 12345))
    assert api().loopback_address(("::1", 12345, 0, 0))
    assert not api().loopback_address(("api.deepseek.com", 443))
    assert not api().loopback_address(("192.168.1.2", 5432))


def test_trace_file_failure_cannot_replace_business_result(monkeypatch, tmp_path):
    from pathlib import Path

    def broken(*args, **kwargs):
        raise OSError("SYNTHETIC_PRIVATE_DISK_FAILURE")

    monkeypatch.setattr(Path, "open", broken)
    assert api().event(tmp_path, "synthetic") is False


def test_private_settings_ignore_ambient_paid_and_external_dependencies(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "DO_NOT_USE_AMBIENT_PAID_KEY")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://production.invalid/db")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    settings = api().isolated_settings(tmp_path)
    assert settings.app_env == "testing" and settings.memory_mode == "M2"
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert str(tmp_path.resolve()).replace("\\", "/") in settings.database_url
    assert not settings.llm_configured and not settings.embedding_configured
    assert not settings.redis_configured and not settings.qdrant_configured
    assert settings.agent_tracing_backend == "local"


async def test_controlled_generation_fault_uses_real_error_category(tmp_path):
    from app.core.exceptions import LLMProviderError
    from app.prompts.answer import ANSWER_SYSTEM

    provider = api().ControlledLLM(tmp_path)
    token = api().FAULT.set("generate_error")
    try:
        with pytest.raises(LLMProviderError):
            await provider.generate(
                [dict(role="system", content=ANSWER_SYSTEM), dict(role="user", content="synthetic")]
            )
    finally:
        api().FAULT.reset(token)


async def test_controlled_generation_uses_evidence_and_returns_valid_json(tmp_path):
    from app.prompts.answer import ANSWER_SYSTEM

    provider = api().ControlledLLM(tmp_path)
    reply = await provider.generate(
        [
            dict(role="system", content=ANSWER_SYSTEM),
            dict(
                role="user",
                content="用户问题：退货政策\n检索证据：\n[doc-chunk] policy\n合成条款可复核\n\n工具结果：\n(无)\n\n输出 JSON：",
            ),
        ]
    )
    body = json.loads(reply.content)
    assert "合成条款可复核" in body["answer"]
    assert body["citation_chunk_ids"] == ["doc-chunk"]
