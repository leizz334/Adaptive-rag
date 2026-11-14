"""Usage settlement invariants using only private temp ledgers and local HTTPX fixtures."""

import asyncio
import hashlib
import json
import multiprocessing
import os
import sqlite3
from decimal import Decimal

import httpx
import pytest

from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetedTransport
from tests.unit.test_paid_budget import ledger, limits, payload

pytestmark = pytest.mark.skipif(os.name == "nt", reason="requires native Linux permissions")
URL = "https://api.deepseek.com/chat/completions"
DIGEST = hashlib.sha256(b"complete response").hexdigest()


def usage(**changes):
    return {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11, **changes}


def result(**changes):
    return {
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "private response"},
                "finish_reason": "stop",
            }
        ],
        "usage": usage(),
        **changes,
    }


def settle(book, attempt, **changes):
    book.settle(attempt, **{**usage(), "response_sha256": DIGEST, "source": "json", **changes})


def test_settlement_preserves_reservations_and_reopens_net_capacity(tmp_path):
    book = ledger(tmp_path, max_tokens=1400)
    attempt = book.reserve(payload())
    raw = book.snapshot()
    with sqlite3.connect(book.path) as conn:
        original = conn.execute("SELECT * FROM attempts").fetchall()
        fingerprint = conn.execute("SELECT * FROM metadata").fetchall()
    settle(book, attempt)
    snapshot = AttemptLedger(book.path, book.limits).snapshot()
    assert snapshot["tokens"] == 11
    assert Decimal(snapshot["usd"]) == Decimal("0.000014")
    assert snapshot["reserved_tokens"] == raw["tokens"]
    assert snapshot["reserved_usd"] == raw["usd"]
    assert snapshot["requests"] == snapshot["completed"] == snapshot["settled"] == 1
    with sqlite3.connect(book.path) as conn:
        after = conn.execute("SELECT * FROM attempts").fetchall()
        assert after[0][:3] == original[0][:3]
        assert conn.execute("SELECT * FROM metadata").fetchall() == fingerprint
    book.reserve(payload())
    assert b"private prompt" not in book.path.read_bytes()
    assert b"private response" not in book.path.read_bytes()


@pytest.mark.parametrize(
    "changes",
    [
        {"prompt_tokens": True},
        {"completion_tokens": 1.0},
        {"total_tokens": "11"},
        {"prompt_tokens": -1},
        {"completion_tokens": -1},
        {"total_tokens": 12},
        {"prompt_tokens": 100000, "total_tokens": 100003},
        {"completion_tokens": 11, "total_tokens": 19},
        {"response_sha256": "private response"},
        {"source": "private header"},
    ],
)
def test_untrusted_counts_or_evidence_never_release_reservation(tmp_path, changes):
    book = ledger(tmp_path)
    attempt = book.reserve(payload())
    before = book.snapshot()
    with pytest.raises(BudgetBlocked):
        settle(book, attempt, **changes)
    assert book.snapshot() == before


def test_settlement_duplicate_is_idempotent_conflict_is_atomic(tmp_path):
    book = ledger(tmp_path)
    attempt = book.reserve(payload())
    settle(book, attempt)
    before = book.snapshot()
    settle(AttemptLedger(book.path, book.limits), attempt)
    assert book.snapshot() == before
    with pytest.raises(BudgetBlocked):
        settle(book, attempt, response_sha256="f" * 64)
    assert book.snapshot() == before
    with pytest.raises(BudgetBlocked):
        settle(book, 999)


@pytest.mark.parametrize("state", ["complete", "uncertain"])
def test_terminal_unsettled_attempt_cannot_be_released(tmp_path, state):
    book = ledger(tmp_path)
    attempt = book.reserve(payload())
    getattr(book, state)(attempt)
    with pytest.raises(BudgetBlocked):
        settle(book, attempt)
    assert book.snapshot()["settled"] == 0


def test_legacy_migration_preserves_all_charges_and_cannot_backfill(tmp_path):
    book = ledger(tmp_path)
    path = book.path
    with sqlite3.connect(path) as conn:
        for name in ("settlements", "reservation_evidence"):
            conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute("INSERT INTO attempts VALUES (42,1234,'0.0123','completed')")
        original = conn.execute("SELECT * FROM attempts").fetchall()
    migrated = AttemptLedger(path, book.limits)
    snapshot = migrated.snapshot()
    assert snapshot["tokens"] == snapshot["reserved_tokens"] == 1234
    assert Decimal(snapshot["usd"]) == Decimal("0.0123")
    assert snapshot["settled"] == 0
    with pytest.raises(BudgetBlocked):
        settle(migrated, 42)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT * FROM attempts").fetchall() == original


async def test_dispatch_disabled_blocks_before_reservation(tmp_path):
    book = ledger(tmp_path)
    async with httpx.AsyncClient(
        transport=BudgetedTransport(
            book,
            httpx.MockTransport(lambda request: pytest.fail("dispatched")),
            dispatch_enabled=False,
        )
    ) as client:
        with pytest.raises(BudgetBlocked):
            await client.post(URL, content=payload())
    assert book.snapshot()["requests"] == 0


async def test_complete_json_settles_only_after_consumption_and_close(tmp_path):
    book = ledger(tmp_path)
    async with httpx.AsyncClient(
        transport=BudgetedTransport(
            book, httpx.MockTransport(lambda request: httpx.Response(200, json=result()))
        )
    ) as client:
        async with client.stream("POST", URL, content=payload()) as response:
            assert book.snapshot()["pending"] == 1
            chunks = [chunk async for chunk in response.aiter_raw()]
            assert chunks
        snapshot = book.snapshot()
        assert snapshot["settled"] == 1
        assert snapshot["tokens"] == 11


@pytest.mark.parametrize(
    "body,status",
    [
        (result(), 429),
        (result(model="wrong"), 200),
        (result(usage=None), 200),
        (result(usage=usage(total_tokens=True)), 200),
        (result(usage=usage(total_tokens=999)), 200),
        (result(choices=[{"finish_reason": "length"}]), 200),
        (result(choices=[]), 200),
        ({"usage": usage()}, 200),
        (b'{"model": "deepseek-chat",', 200),
        (
            b'{"model":"wrong","model":"deepseek-chat","choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":8,"completion_tokens":3,"total_tokens":11}}',
            200,
        ),
    ],
)
async def test_incomplete_or_invalid_json_keeps_full_reservation(tmp_path, body, status):
    book = ledger(tmp_path)
    response = (
        httpx.Response(status, content=body)
        if isinstance(body, bytes)
        else httpx.Response(status, json=body)
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload())
    snapshot = book.snapshot()
    assert snapshot["settled"] == 0
    assert snapshot["tokens"] == snapshot["reserved_tokens"]
    assert snapshot["usd"] == snapshot["reserved_usd"]
    assert snapshot["completed"] == 1


def sse(*, terminal=True, final_usage=True, finish="stop", model="deepseek-chat", extra=b""):
    chunks = [
        {
            "model": model,
            "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
        },
        {"model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
    ]
    if final_usage:
        chunks.append({"model": model, "choices": [], "usage": usage()})
    return (
        b"".join(b"data: " + json.dumps(chunk).encode() + b"\n\n" for chunk in chunks)
        + (b"data: [DONE]\n\n" if terminal else b"")
        + extra
    )


@pytest.mark.parametrize(
    "changes,settled",
    [
        ({}, 1),
        ({"terminal": False}, 0),
        ({"final_usage": False}, 0),
        ({"finish": "length"}, 0),
        ({"model": "wrong"}, 0),
        ({"extra": b'data: {"usage":{}}\n\n'}, 0),
    ],
)
async def test_sse_requires_final_usage_model_finish_and_terminal(tmp_path, changes, settled):
    book = ledger(tmp_path)
    response = httpx.Response(
        200, content=sse(**changes), headers={"content-type": "text/event-stream"}
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=True))
    assert book.snapshot()["settled"] == settled
    assert book.snapshot()["tokens"] == (11 if settled else book.snapshot()["reserved_tokens"])


class ClosingStream(httpx.AsyncByteStream):
    def __init__(self, book, error=None):
        self.book, self.error = book, error

    async def __aiter__(self):
        yield json.dumps(result()).encode()
        assert self.book.snapshot()["pending"] == 1
        assert self.book.snapshot()["settled"] == 0

    async def aclose(self):
        assert self.book.snapshot()["pending"] == 1
        assert self.book.snapshot()["settled"] == 0
        if self.error:
            raise self.error


@pytest.mark.parametrize("error", [None, RuntimeError("private"), asyncio.CancelledError()])
async def test_close_confirmation_required_and_close_failure_blocks(tmp_path, error):
    book = ledger(tmp_path)
    stream = ClosingStream(book, error)
    async with httpx.AsyncClient(
        transport=BudgetedTransport(
            book, httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
        )
    ) as client:
        if error:
            with pytest.raises(
                asyncio.CancelledError
                if isinstance(error, asyncio.CancelledError)
                else BudgetBlocked
            ):
                await client.post(URL, content=payload())
        else:
            await client.post(URL, content=payload())
    snapshot = book.snapshot()
    assert snapshot["settled"] == (0 if error else 1)
    assert snapshot["uncertain"] == (1 if error else 0)


def _settle_process(path, gate, out, digest):
    book = AttemptLedger(path, limits())
    gate.wait(timeout=5)
    try:
        settle(book, 1, response_sha256=digest)
        out.put(True)
    except BudgetBlocked:
        out.put(False)


@pytest.mark.parametrize("conflict", [False, True])
def test_cross_process_settlement_is_atomic_and_restart_durable(tmp_path, conflict):
    book = ledger(tmp_path)
    book.reserve(payload())
    ctx = multiprocessing.get_context("fork")
    gate, out = ctx.Barrier(2), ctx.Queue()
    workers = [
        ctx.Process(
            target=_settle_process,
            args=(book.path, gate, out, "f" * 64 if conflict and i else DIGEST),
        )
        for i in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    assert sorted([out.get(timeout=2), out.get(timeout=2)]) == (
        [False, True] if conflict else [True, True]
    )
    reopened = AttemptLedger(book.path, limits())
    assert reopened.snapshot()["settled"] == 1
    assert reopened.snapshot()["tokens"] == 11
    assert reopened.snapshot()["requests"] == 1


def test_request_cap_is_never_refunded_by_settlement(tmp_path):
    book = ledger(tmp_path, max_requests=1)
    settle(book, book.reserve(payload()))
    with pytest.raises(BudgetBlocked):
        book.reserve(payload())
    assert book.snapshot()["requests"] == 1


def test_settled_cost_allows_next_reservation_under_unchanged_usd_cap(tmp_path):
    book = ledger(tmp_path, max_usd=Decimal("0.0013"))
    settle(book, book.reserve(payload()))
    book.reserve(payload())
    assert book.snapshot()["requests"] == 2
    assert Decimal(book.snapshot()["reserved_usd"]) > book.limits.max_usd
    assert Decimal(book.snapshot()["usd"]) < book.limits.max_usd


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE settlements SET total_tokens=12",
        "UPDATE settlements SET usd='0'",
        "UPDATE settlements SET response_sha256='secret'",
        "UPDATE settlements SET source='secret'",
        "UPDATE settlements SET completion_tokens=99,total_tokens=107",
        "UPDATE reservation_evidence SET input_tokens=1",
        "UPDATE attempts SET state='uncertain'",
        "INSERT INTO reservation_evidence VALUES (999,1,1)",
        "CREATE TABLE unexpected (secret TEXT)",
    ],
)
def test_corrupt_audit_metadata_blocks_reopen_and_admission(tmp_path, sql):
    book = ledger(tmp_path)
    settle(book, book.reserve(payload()))
    with sqlite3.connect(book.path) as conn:
        conn.execute(sql)
    with pytest.raises(BudgetBlocked):
        book.reserve(payload())
    with pytest.raises(BudgetBlocked):
        AttemptLedger(book.path, book.limits)


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, raw, size):
        self.raw, self.size = raw, size

    async def __aiter__(self):
        for offset in range(0, len(self.raw), self.size):
            yield self.raw[offset : offset + self.size]


@pytest.mark.parametrize("size", [1, 7, 16384])
async def test_sse_crlf_survives_arbitrary_transport_boundaries(tmp_path, size):
    book = ledger(tmp_path)
    raw = sse().replace(b"\n", b"\r\n")
    response = httpx.Response(
        200,
        stream=ChunkStream(raw, size),
        headers={"content-type": "text/event-stream; charset=utf-8"},
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=True))
    assert book.snapshot()["tokens"] == 11
    with sqlite3.connect(book.path) as conn:
        assert conn.execute("SELECT response_sha256,source FROM settlements").fetchone() == (
            hashlib.sha256(raw).hexdigest(),
            "sse",
        )


@pytest.mark.parametrize("streaming", [False, True])
async def test_oversized_response_cannot_release_capacity(tmp_path, streaming):
    book = ledger(tmp_path)
    if streaming:
        raw = b"data: " + b" " * 70000 + b"\n\n" + sse()
    else:
        raw = json.dumps(result(extra="x" * 1100000)).encode()
    response = httpx.Response(
        200,
        stream=ChunkStream(raw, 16384),
        headers={"content-type": "text/event-stream" if streaming else "application/json"},
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=streaming))
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["tokens"] == book.snapshot()["reserved_tokens"]


@pytest.mark.parametrize(
    "choices",
    [
        [{"index": 1, "finish_reason": "stop"}],
        [{"index": True, "finish_reason": "stop"}],
        [{"finish_reason": ["stop"]}],
    ],
)
async def test_ambiguous_choice_metadata_keeps_reservation(tmp_path, choices):
    book = ledger(tmp_path)
    response = httpx.Response(200, json=result(choices=choices))
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload())
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["completed"] == 1


async def test_concurrent_response_close_cannot_double_finalize(tmp_path):
    book = ledger(tmp_path)

    class YieldOnClose(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield json.dumps(result()).encode()

        async def aclose(self):
            await asyncio.sleep(0)

    transport = BudgetedTransport(
        book, httpx.MockTransport(lambda request: httpx.Response(200, stream=YieldOnClose()))
    )
    response = await transport.handle_async_request(httpx.Request("POST", URL, content=payload()))
    assert [chunk async for chunk in response.stream]
    assert book.snapshot()["pending"] == 1
    await asyncio.gather(response.stream.aclose(), response.stream.aclose())
    assert book.snapshot()["settled"] == book.snapshot()["completed"] == 1
    assert book.snapshot()["tokens"] == 11
    await transport.aclose()


@pytest.mark.parametrize("streaming", [False, True])
async def test_provider_error_metadata_never_releases_capacity(tmp_path, streaming):
    book = ledger(tmp_path)
    raw = (
        sse().replace(b'"model": ', b'"error": {"message": "failed"}, "model": ', 1)
        if streaming
        else json.dumps(result(error={"message": "failed"})).encode()
    )
    response = httpx.Response(
        200,
        content=raw,
        headers={"content-type": "text/event-stream" if streaming else "application/json"},
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=streaming))
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["tokens"] == book.snapshot()["reserved_tokens"]


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "stop"},
        {"finish_reason": "stop", "message": None},
        {"finish_reason": "stop", "message": "wrong"},
        {"finish_reason": "stop", "message": {}},
        {"finish_reason": "stop", "message": {"content": None}},
        {"finish_reason": "stop", "message": {"content": 3}},
        {"finish_reason": "stop", "message": {"role": "user", "content": "wrong role"}},
        {"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": []}},
        {
            "finish_reason": "tool_calls",
            "message": {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": 1},
                    }
                ],
            },
        },
        {
            "finish_reason": "tool_calls",
            "message": {
                "content": None,
                "tool_calls": [
                    {"type": "function", "function": {"name": "lookup", "arguments": "{}"}}
                ],
            },
        },
        {"finish_reason": "stop", "message": {"content": "text", "tool_calls": "wrong"}},
        {"finish_reason": "function_call", "message": {"content": None}},
    ],
)
async def test_protocol_invalid_json_message_keeps_full_reservation(tmp_path, choice):
    book = ledger(tmp_path)
    response = httpx.Response(200, json=result(choices=[choice]))
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload())
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["tokens"] == book.snapshot()["reserved_tokens"]
    assert book.snapshot()["completed"] == 1


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "stop", "message": {"content": ""}},
        {
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": "{}"},
                    }
                ],
            },
        },
        {
            "finish_reason": "function_call",
            "message": {"content": None, "function_call": {"name": "lookup", "arguments": "{}"}},
        },
    ],
)
async def test_protocol_valid_empty_text_or_typed_tool_calls_can_settle(tmp_path, choice):
    book = ledger(tmp_path)
    response = httpx.Response(200, json=result(choices=[choice]))
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload())
    assert book.snapshot()["settled"] == 1
    assert book.snapshot()["tokens"] == 11


@pytest.mark.parametrize(
    "choice",
    [
        {"index": 0, "finish_reason": "stop"},
        {"index": 0, "delta": None, "finish_reason": "stop"},
        {"index": 0, "delta": "invalid", "finish_reason": "stop"},
        {"index": 0, "delta": {"role": "user"}, "finish_reason": "stop"},
        {"index": 0, "delta": {"content": 3}, "finish_reason": "stop"},
        {"index": 0, "delta": {"content": {"text": "wrong"}}, "finish_reason": "stop"},
        {"index": 0, "delta": {"tool_calls": "invalid"}, "finish_reason": "tool_calls"},
        {
            "index": 0,
            "delta": {"tool_calls": [{"index": True, "function": {"arguments": "{}"}}]},
            "finish_reason": "tool_calls",
        },
        {
            "index": 0,
            "delta": {"tool_calls": [{"index": 0, "function": {"arguments": 3}}]},
            "finish_reason": "tool_calls",
        },
        {
            "index": 0,
            "delta": {
                "tool_calls": [{"index": 0, "type": "wrong", "function": {"arguments": "{}"}}]
            },
            "finish_reason": "tool_calls",
        },
        {
            "index": 0,
            "delta": {"function_call": {"arguments": 3}},
            "finish_reason": "function_call",
        },
    ],
)
async def test_protocol_invalid_sse_delta_keeps_full_reservation(tmp_path, choice):
    book = ledger(tmp_path)
    chunks = [
        {"model": "deepseek-chat", "choices": [choice]},
        {"model": "deepseek-chat", "choices": [], "usage": usage()},
    ]
    raw = (
        b"".join(b"data: " + json.dumps(chunk).encode() + b"\n\n" for chunk in chunks)
        + b"data: [DONE]\n\n"
    )
    response = httpx.Response(200, content=raw, headers={"content-type": "text/event-stream"})
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=True))
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["tokens"] == book.snapshot()["reserved_tokens"]
    assert book.snapshot()["completed"] == 1


@pytest.mark.parametrize(
    "delta,reason",
    [
        ({"role": "assistant", "content": None}, "stop"),
        (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": "{}"},
                    }
                ]
            },
            "tool_calls",
        ),
        ({"tool_calls": [{"index": 0, "function": {"arguments": "}"}}]}, "tool_calls"),
        ({"function_call": {"name": "lookup", "arguments": "{}"}}, "function_call"),
    ],
)
async def test_protocol_valid_sse_delta_and_tool_fragments_can_settle(tmp_path, delta, reason):
    book = ledger(tmp_path)
    chunks = [
        {
            "model": "deepseek-chat",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        },
        {"model": "deepseek-chat", "choices": [{"index": 0, "delta": {}, "finish_reason": reason}]},
        {"model": "deepseek-chat", "choices": [], "usage": usage()},
    ]
    raw = (
        b"".join(b"data: " + json.dumps(chunk).encode() + b"\n\n" for chunk in chunks)
        + b"data: [DONE]\n\n"
    )
    response = httpx.Response(200, content=raw, headers={"content-type": "text/event-stream"})
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=True))
    assert book.snapshot()["settled"] == 1
    assert book.snapshot()["tokens"] == 11


def inline_usage_sse(*, variant="valid"):
    first = {
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
        "usage": None,
    }
    final = {
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": usage(),
    }
    if variant == "early":
        first["usage"] = usage()
    elif variant == "error":
        final["error"] = {"message": "failed"}
    elif variant == "truncated":
        final["choices"][0]["finish_reason"] = "length"
    elif variant == "content":
        final["choices"][0]["delta"] = {"content": "unexpected content in usage event"}
    elif variant == "mismatch":
        final["usage"] = usage(total_tokens=999)
    chunks = [first, final]
    if variant == "duplicate":
        chunks.append(final)
    elif variant == "separate_duplicate":
        chunks.append({"model": "deepseek-chat", "choices": [], "usage": usage()})
    return b"".join(b"data: " + json.dumps(chunk).encode() + b"\n\n" for chunk in chunks) + (
        b"" if variant == "no_done" else b"data: [DONE]\n\n"
    )


async def test_documented_sse_final_choice_usage_settles_only_after_close(tmp_path):
    book = ledger(tmp_path)
    raw = inline_usage_sse()
    transport = BudgetedTransport(
        book,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, stream=ChunkStream(raw, 7), headers={"content-type": "text/event-stream"}
            )
        ),
    )
    response = await transport.handle_async_request(
        httpx.Request("POST", URL, content=payload(stream=True))
    )
    assert b"".join([chunk async for chunk in response.stream]) == raw
    assert book.snapshot()["pending"] == 1
    assert book.snapshot()["settled"] == 0
    await response.stream.aclose()
    assert book.snapshot()["settled"] == 1
    assert book.snapshot()["tokens"] == 11
    await transport.aclose()


@pytest.mark.parametrize(
    "variant",
    [
        "early",
        "error",
        "truncated",
        "content",
        "mismatch",
        "duplicate",
        "separate_duplicate",
        "no_done",
    ],
)
async def test_inline_sse_usage_invalid_or_duplicate_keeps_reservation(tmp_path, variant):
    book = ledger(tmp_path)
    response = httpx.Response(
        200,
        content=inline_usage_sse(variant=variant),
        headers={"content-type": "text/event-stream"},
    )
    async with httpx.AsyncClient(
        transport=BudgetedTransport(book, httpx.MockTransport(lambda request: response))
    ) as client:
        await client.post(URL, content=payload(stream=True))
    assert book.snapshot()["settled"] == 0
    assert book.snapshot()["tokens"] == book.snapshot()["reserved_tokens"]
