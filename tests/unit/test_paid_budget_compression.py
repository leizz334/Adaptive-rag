"""Observe decoded provider entities using local compressed HTTP fixtures."""

import asyncio
import gzip
import hashlib
import json
import os
import sqlite3
import zlib

import httpx
import pytest
from pydantic import SecretStr

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider
from app.providers.paid_budget import BudgetBlocked, BudgetedTransport
from tests.unit.test_paid_budget import ledger, payload
from tests.unit.test_usage_settlement import ChunkStream, result, sse

pytestmark = pytest.mark.skipif(os.name == "nt", reason="requires Linux permissions")


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
@pytest.mark.parametrize("streaming", [False, True])
async def test_compressed_provider_success_settles_decoded_usage(tmp_path, encoding, streaming):
    book = ledger(tmp_path)
    raw = sse() if streaming else json.dumps(result()).encode()
    compressed = gzip.compress(raw) if encoding == "gzip" else zlib.compress(raw)
    settings = Settings(_env_file=None, deepseek_api_key=SecretStr("fake-test-key"))

    def handler(request):
        return httpx.Response(
            200,
            stream=ChunkStream(compressed, 7),
            headers={
                "content-type": "text/event-stream" if streaming else "application/json",
                "content-encoding": encoding,
                "content-length": str(len(compressed)),
            },
        )

    async with httpx.AsyncClient(
        base_url=settings.deepseek_base_url,
        transport=BudgetedTransport(book, httpx.MockTransport(handler)),
    ) as client:
        provider = DeepSeekProvider(settings, client)
        messages = [{"role": "user", "content": "test"}]
        if streaming:
            assert [chunk async for chunk in provider.stream(messages, max_tokens=10)] == ["hello"]
        else:
            generated = await provider.generate(messages, max_tokens=10)
            assert generated.content == "private response"
            assert generated.usage.total_tokens == 11
    snapshot = book.snapshot()
    assert snapshot["completed"] == snapshot["settled"] == 1
    assert snapshot["tokens"] == 11
    with sqlite3.connect(book.path) as conn:
        assert conn.execute("SELECT response_sha256 FROM settlements").fetchone() == (
            hashlib.sha256(raw).hexdigest(),
        )


@pytest.mark.parametrize("failure", [None, "close", "cancel", "partial", "decode"])
async def test_decoded_entity_settles_only_after_consumption_and_confirmed_close(tmp_path, failure):
    book = ledger(tmp_path)
    raw = json.dumps(result()).encode()

    class CompressedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"invalid-gzip" if failure == "decode" else gzip.compress(raw)
            assert book.snapshot()["pending"] == 1
            assert book.snapshot()["settled"] == 0

        async def aclose(self):
            assert book.snapshot()["settled"] == 0
            if failure == "close":
                raise RuntimeError("fixture close failed")
            if failure == "cancel":
                raise asyncio.CancelledError()

    transport = BudgetedTransport(
        book,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                stream=CompressedStream(),
                headers={
                    "content-type": "application/json",
                    "content-encoding": "gzip",
                    "content-length": "999",
                },
            )
        ),
    )
    response = await transport.handle_async_request(
        httpx.Request("POST", "https://api.deepseek.com/chat/completions", content=payload())
    )
    assert "content-encoding" not in response.headers
    assert "content-length" not in response.headers
    if failure in {"close", "cancel", "decode"}:
        with pytest.raises(asyncio.CancelledError if failure == "cancel" else BudgetBlocked):
            _ = [chunk async for chunk in response.stream]
    elif failure == "partial":
        iterator = response.stream.__aiter__()
        assert await anext(iterator) == raw
        with pytest.raises(BudgetBlocked):
            await response.stream.aclose()
        await iterator.aclose()
    else:
        assert b"".join([chunk async for chunk in response.stream]) == raw
        assert book.snapshot()["settled"] == 0
        await response.stream.aclose()
    assert book.snapshot()["settled"] == (0 if failure else 1)
    assert book.snapshot()["uncertain"] == (1 if failure else 0)
    await transport.aclose()
