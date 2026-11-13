"""Paid transport admission: local fixtures only, never a live provider."""

import asyncio
import json
import multiprocessing
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from app.config.settings import Settings
from app.core.exceptions import AppError, LLMProviderError
from app.providers.deepseek import DeepSeekProvider
from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetedTransport, BudgetLimits

pytestmark = pytest.mark.skipif(os.name == "nt", reason="paid ledger requires Linux permissions")


def limits(**changes):
    return replace(
        BudgetLimits(10, 100_000, Decimal("1"), Decimal("1"), Decimal("2"), "deepseek-chat"),
        **changes,
    )


def payload(**changes):
    return json.dumps(
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "private prompt"}],
            "max_tokens": 10,
            **changes,
        }
    ).encode()


def ledger(tmp_path, **changes):
    return AttemptLedger(tmp_path / "private" / "budget.sqlite", limits(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"max_requests": True},
        {"max_tokens": 0},
        {"max_usd": Decimal("NaN")},
        {"input_usd_per_million": Decimal("Infinity")},
        {"output_usd_per_million": Decimal("0")},
        {"model": ""},
    ],
)
def test_invalid_limits_rejected(changes):
    with pytest.raises((ValueError, BudgetBlocked)):
        limits(**changes)


@pytest.mark.parametrize(
    "changes", [{"max_requests": 1}, {"max_tokens": 1}, {"max_usd": Decimal("0.000001")}]
)
async def test_caps_block_before_dispatch(tmp_path, changes):
    book = ledger(tmp_path, **changes)
    dispatched = []

    def handler(request):
        dispatched.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(handler))
    ) as client:
        if "max_requests" in changes:
            await client.post("https://api.deepseek.com/chat/completions", content=payload())
        with pytest.raises(BudgetBlocked) as caught:
            await client.post("https://api.deepseek.com/chat/completions", content=payload())
    assert len(dispatched) == (1 if "max_requests" in changes else 0)
    assert isinstance(caught.value, AppError)
    assert not isinstance(caught.value, LLMProviderError)
    assert caught.value.retryable is False
    assert caught.value.http_status == 503


def test_reservations_durable_no_content_or_refunds(tmp_path):
    book = ledger(tmp_path)
    attempt = book.reserve(payload())
    snapshot = book.snapshot()
    assert snapshot["requests"] == 1
    assert snapshot["tokens"] >= len(payload()) + 10
    assert Decimal(snapshot["usd"]) > Decimal("0")
    with pytest.raises(BudgetBlocked):
        AttemptLedger(book.path, limits()).ensure_ready()
    book.complete(attempt)
    reopened = AttemptLedger(book.path, limits())
    reopened.ensure_ready()
    assert reopened.snapshot()["tokens"] == snapshot["tokens"]
    assert reopened.snapshot()["completed"] == 1
    assert b"private prompt" not in book.path.read_bytes()
    if os.name != "nt":
        assert book.path.stat().st_mode & 0o777 == 0o600
        assert book.path.parent.stat().st_mode & 0o777 == 0o700
    with pytest.raises(BudgetBlocked):
        AttemptLedger(book.path, limits(max_requests=20))


def test_atomic_admission_two_instances(tmp_path):
    first = ledger(tmp_path)
    second = AttemptLedger(first.path, limits())

    def reserve(book):
        try:
            return book.reserve(payload())
        except BudgetBlocked:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(reserve, [first, second]))
    assert sum(value is not None for value in results) == 1
    assert first.snapshot()["requests"] == 1


def _reserve_process(path, gate, results):
    book = AttemptLedger(path, limits())
    gate.wait(timeout=5)
    try:
        book.reserve(payload())
        results.put(True)
    except BudgetBlocked:
        results.put(False)


def test_atomic_admission_across_processes(tmp_path):
    book = ledger(tmp_path)
    context = multiprocessing.get_context("fork")
    gate = context.Barrier(2)
    results = context.Queue()
    workers = [
        context.Process(target=_reserve_process, args=(book.path, gate, results)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    assert sorted([results.get(timeout=2), results.get(timeout=2)]) == [False, True]
    assert book.snapshot()["requests"] == 1


def test_unknown_and_uncertain_attempts_fail_closed(tmp_path):
    book = ledger(tmp_path)
    with pytest.raises(BudgetBlocked):
        book.complete(999)
    attempt = book.reserve(payload())
    book.uncertain(attempt)
    with pytest.raises(BudgetBlocked):
        book.complete(attempt)
    with pytest.raises(BudgetBlocked):
        book.reserve(payload())
    assert book.snapshot()["uncertain"] == 1


def test_corrupted_accounting_is_generic_and_blocks(tmp_path):
    book = ledger(tmp_path)
    book.complete(book.reserve(payload()))
    with sqlite3.connect(book.path) as connection:
        connection.execute("UPDATE attempts SET usd='sensitive-invalid-cost'")
    with pytest.raises(BudgetBlocked):
        book.reserve(payload())


@pytest.mark.parametrize("foreign", [False, True])
def test_corrupt_or_foreign_ledger_generic_error(tmp_path, foreign):
    path = tmp_path / "foreign.sqlite"
    if foreign:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE unrelated (secret TEXT)")
    else:
        path.write_text("secret-corrupt-content")
    with pytest.raises(BudgetBlocked) as caught:
        AttemptLedger(path, limits())
    assert "secret" not in str(caught.value)


def test_symlink_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege unavailable")
    with pytest.raises(BudgetBlocked):
        AttemptLedger(link / "budget.sqlite", limits())


@pytest.mark.parametrize(
    "url,changes",
    [
        ("http://api.deepseek.com/chat/completions", {}),
        ("https://example.org/chat/completions", {}),
        ("https://api.deepseek.com/other", {}),
        ("https://api.deepseek.com/chat/completions?x=1", {}),
        ("https://api.deepseek.com/chat/completions", {"model": "other"}),
        ("https://api.deepseek.com/chat/completions", {"max_tokens": True}),
    ],
)
async def test_invalid_target_or_payload_never_admitted(tmp_path, url, changes):
    book = ledger(tmp_path)

    def handler(request):
        pytest.fail("invalid request dispatched")

    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(handler))
    ) as client:
        with pytest.raises(BudgetBlocked):
            await client.post(url, content=payload(**changes))
    assert book.snapshot()["requests"] == 0


class BrokenStream(httpx.AsyncByteStream):
    def __init__(self, error=None):
        self.error = error

    async def __aiter__(self):
        yield b"data: partial\n\n"
        if self.error:
            raise self.error
        yield b"data: [DONE]\n\n"


@pytest.mark.parametrize("failure", ["network", "stream", "cancel", "read_cancel", "partial"])
async def test_uncertainty_blocks_without_retry(tmp_path, failure):
    book = ledger(tmp_path)

    async def handler(request):
        if failure == "network":
            raise httpx.ConnectError("private network details")
        if failure == "cancel":
            raise asyncio.CancelledError()
        if failure == "read_cancel":
            return httpx.Response(200, stream=BrokenStream(asyncio.CancelledError()))
        return httpx.Response(
            200, stream=BrokenStream(httpx.ReadError("private") if failure == "stream" else None)
        )

    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(handler))
    ) as client:
        if failure == "partial":
            with pytest.raises(BudgetBlocked):
                async with client.stream(
                    "POST", "https://api.deepseek.com/chat/completions", content=payload()
                ) as response:
                    async for _ in response.aiter_bytes():
                        break
        else:
            with pytest.raises(
                asyncio.CancelledError if failure in {"cancel", "read_cancel"} else BudgetBlocked
            ):
                await client.post("https://api.deepseek.com/chat/completions", content=payload())
    assert book.snapshot()["uncertain"] == 1
    assert book.snapshot()["requests"] == 1
    with pytest.raises(BudgetBlocked):
        book.ensure_ready()


async def test_provider_429_retries_reserve_every_attempt(tmp_path, monkeypatch):
    book = ledger(tmp_path, max_requests=2)
    monkeypatch.setattr("app.core.retry._full_jitter_delay", lambda *args: 0)
    settings = Settings(
        _env_file=None, deepseek_api_key=SecretStr("fake-test-key"), llm_max_retries=3
    )
    async with httpx.AsyncClient(
        base_url=settings.deepseek_base_url,
        transport=BudgetedTransport(
            book, httpx.MockTransport(lambda request: httpx.Response(429, json={}))
        ),
    ) as client:
        with pytest.raises(BudgetBlocked):
            await DeepSeekProvider(settings, client).generate(
                [{"role": "user", "content": "test"}], max_tokens=10
            )
    assert book.snapshot()["requests"] == 2
    assert book.snapshot()["completed"] == 2


async def test_provider_json_and_sse_fully_consumed(tmp_path):
    book = ledger(tmp_path)
    settings = Settings(_env_file=None, deepseek_api_key=SecretStr("fake-test-key"))

    def handler(request):
        if json.loads(request.content).get("stream"):
            return httpx.Response(
                200,
                content=b'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
                headers={"Content-Type": "text/event-stream"},
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}]}
        )

    async with httpx.AsyncClient(
        base_url=settings.deepseek_base_url,
        transport=BudgetedTransport(book, httpx.MockTransport(handler)),
    ) as client:
        provider = DeepSeekProvider(settings, client)
        assert (
            await provider.generate([{"role": "user", "content": "test"}], max_tokens=10)
        ).content == "hello"
        assert [
            chunk
            async for chunk in provider.stream([{"role": "user", "content": "test"}], max_tokens=10)
        ] == ["hello"]
    assert book.snapshot()["completed"] == 2
    book.ensure_ready()
