"""Additional same-ledger grants: local SQLite and mock HTTP only."""

import multiprocessing
import os
import sqlite3
from decimal import Decimal

import httpx
import pytest

from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetedTransport
from tests.unit.test_paid_budget import ledger, limits, payload
from tests.unit.test_usage_settlement import settle

pytestmark = pytest.mark.skipif(os.name == "nt", reason="requires Linux permissions")
GRANT = "business-acceptance-01"


def authorize(book, **changes):
    book.authorize(GRANT, **{"max_requests": 20, "max_usd": Decimal(".05"), **changes})
    return AttemptLedger(book.path, book.limits, authorization_id=GRANT)


def test_grant_adds_capacity_without_mutating_original_history_or_fingerprint(tmp_path):
    book = ledger(tmp_path, max_requests=1, max_tokens=1400)
    settle(book, book.reserve(payload()))
    with sqlite3.connect(book.path) as conn:
        old = {
            name: conn.execute(f"SELECT * FROM {name}").fetchall()
            for name in ("metadata", "attempts", "reservation_evidence", "settlements")
        }
    active = authorize(book)
    before = active.snapshot()
    active.check_capacity(payload(max_tokens=2000))
    assert active.snapshot() == before
    settle(active, active.reserve(payload(max_tokens=2000)))
    assert active.snapshot()["requests"] == 2
    assert active.snapshot()["authorization"]["requests"] == 1
    grant = active.authorization_snapshot()
    assert grant["identifier"] == GRANT
    assert grant["max_requests"] == 20
    assert grant["max_tokens"] is None
    assert Decimal(grant["max_usd"]) == Decimal(".05")
    assert grant["tokens"] == 11
    assert Decimal(grant["usd"]) == Decimal(".000014")
    with sqlite3.connect(book.path) as conn:
        for name, records in old.items():
            assert conn.execute(f"SELECT * FROM {name}").fetchall()[: len(records)] == records
    with pytest.raises(BudgetBlocked):
        AttemptLedger(book.path, limits(max_requests=2, max_tokens=1400))


def test_request_limit_exactly_twenty_not_refunded_and_survives_restart(tmp_path):
    active = authorize(ledger(tmp_path))
    for _ in range(20):
        active = AttemptLedger(active.path, active.limits, authorization_id=GRANT)
        settle(active, active.reserve(payload()))
    assert active.authorization_snapshot()["requests"] == 20
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload())
    with pytest.raises(BudgetBlocked):
        active.reserve(payload())
    assert active.snapshot()["requests"] == 20


def test_grant_net_fee_cap_released_only_by_trusted_settlement(tmp_path):
    active = authorize(ledger(tmp_path), max_usd=Decimal(".0013"))
    first = active.reserve(payload())
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload())
    settle(active, first)
    active.check_capacity(payload())
    active.complete(active.reserve(payload()))
    with pytest.raises(BudgetBlocked):
        active.reserve(payload())
    assert Decimal(active.authorization_snapshot()["reserved_usd"]) > Decimal(".0013")
    assert Decimal(active.authorization_snapshot()["usd"]) < Decimal(".0013")


def test_optional_grant_token_cap_is_enforced(tmp_path):
    active = authorize(ledger(tmp_path), max_tokens=1)
    with pytest.raises(BudgetBlocked):
        active.reserve(payload())
    assert active.snapshot()["requests"] == 0


def test_duplicate_grant_exact_replay_and_conflict_rejection(tmp_path):
    book = ledger(tmp_path)
    active = authorize(book)
    before = active.snapshot()
    authorize(book, max_usd=Decimal(".050"))
    assert active.snapshot() == before
    for changes in ({"max_requests": 21}, {"max_usd": Decimal(".06")}, {"max_tokens": 100}):
        with pytest.raises(BudgetBlocked):
            authorize(book, **changes)
    with pytest.raises(BudgetBlocked):
        book.authorize("overlap", max_requests=20, max_usd=Decimal(".05"))


@pytest.mark.parametrize(
    "changes",
    [
        {"max_requests": True},
        {"max_requests": 0},
        {"max_requests": 2**63},
        {"max_usd": Decimal("NaN")},
        {"max_usd": Decimal("Infinity")},
        {"max_usd": Decimal("0")},
        {"max_usd": 0.05},
        {"max_tokens": True},
        {"max_tokens": 0},
        {"max_tokens": 2**63},
    ],
)
def test_invalid_grants_never_create_authority(tmp_path, changes):
    book = ledger(tmp_path)
    with pytest.raises(BudgetBlocked):
        authorize(book, **changes)
    assert book.authorization_snapshot() is None
    book.reserve(payload())


def test_no_legacy_or_unknown_selected_id_can_fallback_after_any_grant(tmp_path):
    book = ledger(tmp_path)
    active = authorize(book)
    for candidate in (
        book,
        AttemptLedger(book.path, book.limits),
        AttemptLedger(book.path, book.limits, authorization_id="unknown"),
    ):
        candidate.ensure_ready()
        for method in (candidate.reserve, candidate.check_capacity):
            with pytest.raises(BudgetBlocked):
                method(payload())
    active.close_authorization(GRANT)
    active.ensure_ready()
    for candidate in (book, active, AttemptLedger(book.path, book.limits, authorization_id=GRANT)):
        with pytest.raises(BudgetBlocked):
            candidate.reserve(payload())


def test_closure_is_permanent_idempotent_and_allows_distinct_later_grant(tmp_path):
    book = ledger(tmp_path)
    active = authorize(book)
    settle(active, active.reserve(payload()))
    active.close_authorization(GRANT)
    active.close_authorization(GRANT)
    authorize(book)  # Replaying original grant does not reopen it.
    assert active.authorization_snapshot()["closed"] is True
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload())
    book.authorize("next", max_requests=1, max_usd=Decimal(".01"))
    next_book = AttemptLedger(book.path, book.limits, authorization_id="next")
    assert next_book.authorization_snapshot()["requests"] == 0
    next_book.complete(next_book.reserve(payload()))
    assert active.authorization_snapshot()["requests"] == 1


def test_closed_grant_cannot_be_reopened_by_flipping_mutable_state(tmp_path):
    active = authorize(ledger(tmp_path))
    active.close_authorization(GRANT)
    with sqlite3.connect(active.path) as conn:
        conn.execute("UPDATE authorizations SET closed=0")
    with pytest.raises(BudgetBlocked):
        active.reserve(payload())
    with pytest.raises(BudgetBlocked):
        AttemptLedger(active.path, active.limits, authorization_id=GRANT)


@pytest.mark.parametrize("uncertain", [False, True])
def test_unresolved_attempts_block_new_grants_and_capacity(tmp_path, uncertain):
    book = ledger(tmp_path)
    attempt = book.reserve(payload())
    if uncertain:
        book.uncertain(attempt)
    with pytest.raises(BudgetBlocked):
        authorize(book)


@pytest.mark.parametrize("uncertain", [False, True])
def test_unresolved_grant_attempt_blocks_close_and_admission(tmp_path, uncertain):
    active = authorize(ledger(tmp_path))
    attempt = active.reserve(payload())
    if uncertain:
        active.uncertain(attempt)
    for operation in (
        lambda: active.close_authorization(GRANT),
        lambda: active.check_capacity(payload()),
        lambda: active.reserve(payload()),
    ):
        with pytest.raises(BudgetBlocked):
            operation()


def _grant_worker(path, original_limits, gate, out, operation):
    book = AttemptLedger(path, original_limits, authorization_id=GRANT)
    gate.wait(timeout=5)
    try:
        if operation == "authorize":
            authorize(book)
        else:
            book.reserve(payload())
        out.put(True)
    except BudgetBlocked:
        out.put(False)


@pytest.mark.parametrize("operation", ["authorize", "reserve"])
def test_grants_are_atomic_across_processes(tmp_path, operation):
    book = ledger(tmp_path)
    if operation == "reserve":
        authorize(book)
    ctx = multiprocessing.get_context("fork")
    gate, out = ctx.Barrier(2), ctx.Queue()
    workers = [
        ctx.Process(target=_grant_worker, args=(book.path, book.limits, gate, out, operation))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    assert sorted([out.get(timeout=2), out.get(timeout=2)]) == (
        [True, True] if operation == "authorize" else [False, True]
    )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM attempt_authorizations",
        "UPDATE attempt_authorizations SET authorization_id=999",
        "UPDATE authorizations SET max_usd='NaN'",
        "UPDATE authorizations SET max_usd='1'",
        "UPDATE authorizations SET max_requests=100",
        "UPDATE authorizations SET start_after=999",
        "UPDATE authorizations SET closed=2",
        "UPDATE metadata SET fingerprint='other'",
        "CREATE TABLE unknown (x TEXT)",
    ],
)
def test_invalid_grant_audit_fails_closed(tmp_path, sql):
    active = authorize(ledger(tmp_path))
    active.complete(active.reserve(payload()))
    with sqlite3.connect(active.path) as conn:
        conn.execute(sql)
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload())
    with pytest.raises(BudgetBlocked):
        AttemptLedger(active.path, active.limits, authorization_id=GRANT)


async def test_grant_counts_every_http_retry_against_twenty_attempts(tmp_path):
    active = authorize(ledger(tmp_path))
    async with httpx.AsyncClient(
        transport=BudgetedTransport(
            active, httpx.MockTransport(lambda request: httpx.Response(429, json={}))
        )
    ) as client:
        for _ in range(20):
            assert (
                await client.post("https://api.deepseek.com/chat/completions", content=payload())
            ).status_code == 429
        with pytest.raises(BudgetBlocked):
            await client.post("https://api.deepseek.com/chat/completions", content=payload())
    assert active.authorization_snapshot()["requests"] == 20
    assert active.authorization_snapshot()["completed"] == 20


def test_original_attempt_cannot_be_reassigned_to_additional_grant(tmp_path):
    book = ledger(tmp_path)
    book.complete(book.reserve(payload()))
    active = authorize(book)
    with sqlite3.connect(book.path) as conn:
        conn.execute("INSERT INTO attempt_authorizations VALUES (1,1)")
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload())


def test_whole_request_reservation_must_fit_even_with_no_token_cap(tmp_path):
    active = authorize(ledger(tmp_path))
    with pytest.raises(BudgetBlocked):
        active.check_capacity(payload(max_tokens=30_000))
    with pytest.raises(BudgetBlocked):
        active.reserve(payload(max_tokens=30_000))
    assert active.authorization_snapshot()["requests"] == 0


def test_unknown_selection_cannot_spend_original_budget_before_grant_exists(tmp_path):
    book = ledger(tmp_path)
    unknown = AttemptLedger(book.path, book.limits, authorization_id="unknown")
    assert unknown.authorization_snapshot() is None
    with pytest.raises(BudgetBlocked):
        unknown.reserve(payload())
    assert unknown.snapshot()["requests"] == 0
