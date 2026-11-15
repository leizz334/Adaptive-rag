"""Durable grant crash/closure boundaries using local fake supplier responses only."""

import asyncio
import json
import multiprocessing
import os
import sqlite3
from decimal import Decimal

import httpx
import pytest

from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetedTransport, BudgetLimits

pytestmark = pytest.mark.skipif(os.name == "nt", reason="native Linux permission boundary")


def limits():
    return BudgetLimits(1, 1, Decimal("0.05"), Decimal("0.30"), Decimal("1.20"), "deepseek-flash")


def payload():
    return json.dumps(
        {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "synthetic"}],
            "max_tokens": 8,
        }
    ).encode()


def book(tmp_path):
    admin = AttemptLedger(tmp_path / "private" / "ledger.sqlite3", limits())
    admin.authorize("safety", max_requests=20, max_usd=Decimal("0.05"), max_tokens=None)
    return AttemptLedger(admin.path, limits(), authorization_id="safety")


@pytest.mark.parametrize("tamper", ["orphan", "deleted_witness"])
def test_grant_closure_witness_corruption_fails_closed(tmp_path, tamper):
    ledger = book(tmp_path)
    if tamper == "deleted_witness":
        ledger.close_authorization("safety")
    with sqlite3.connect(ledger.path) as db:
        if tamper == "orphan":
            db.execute("INSERT INTO authorization_closures VALUES (999)")
        else:
            db.execute("DELETE FROM authorization_closures")
    with pytest.raises(BudgetBlocked):
        AttemptLedger(ledger.path, limits(), authorization_id="safety")


def exit_after_reservation(path):
    ledger = AttemptLedger(path, limits(), authorization_id="safety")
    ledger.reserve(payload())
    os._exit(0)


def test_process_exit_preserves_pending_and_blocks_new_authority(tmp_path):
    ledger = book(tmp_path)
    child = multiprocessing.get_context("fork").Process(
        target=exit_after_reservation, args=(ledger.path,)
    )
    child.start()
    child.join(10)
    assert not child.is_alive() and child.exitcode == 0
    reopened = AttemptLedger(ledger.path, limits(), authorization_id="safety")
    assert reopened.snapshot()["pending"] == 1
    for operation in [
        reopened.ensure_ready,
        lambda: reopened.check_capacity(payload()),
        lambda: reopened.reserve(payload()),
        lambda: reopened.close_authorization("safety"),
        lambda: reopened.authorize("new", max_requests=20, max_usd=Decimal("0.05")),
    ]:
        with pytest.raises(BudgetBlocked):
            operation()


async def test_grant_cannot_close_before_supplier_response_close_completes(tmp_path):
    ledger = book(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    data = json.dumps(
        {
            "model": "deepseek-flash",
            "choices": [
                {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        }
    ).encode()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield data

        async def aclose(self):
            entered.set()
            await release.wait()

    async def respond(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, stream=Stream())

    async with httpx.AsyncClient(
        transport=BudgetedTransport(ledger, httpx.MockTransport(respond))
    ) as client:
        task = asyncio.create_task(
            client.post("https://api.deepseek.com/chat/completions", content=payload())
        )
        await asyncio.wait_for(entered.wait(), 3)
        with pytest.raises(BudgetBlocked):
            ledger.close_authorization("safety")
        assert ledger.authorization_snapshot()["pending"] == 1
        release.set()
        response = await task
        assert response.status_code == 200 and ledger.authorization_snapshot()["settled"] == 1
        ledger.close_authorization("safety")
        assert ledger.authorization_snapshot()["closed"]
