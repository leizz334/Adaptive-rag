"""The live run's exact aggregate ceilings survive restarts and deny before send."""

import json
from decimal import Decimal

import pytest

from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetLimits


def limits():
    return BudgetLimits(
        6, 10000, Decimal("0.05"), Decimal("0.30"), Decimal("1.20"), "deepseek-flash"
    )


def payload(text="hi", output=32):
    return json.dumps(
        {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": text}],
            "max_tokens": output,
        }
    ).encode()


def test_exact_request_ceiling_survives_every_restart(tmp_path):
    for count in range(6):
        ledger = AttemptLedger(tmp_path / "budget.sqlite3", limits())
        ledger.complete(ledger.reserve(payload()))
        assert ledger.snapshot()["requests"] == count + 1
    ledger = AttemptLedger(tmp_path / "budget.sqlite3", limits())
    with pytest.raises(BudgetBlocked):
        ledger.reserve(payload())
    assert ledger.snapshot()["requests"] == 6
    assert ledger.snapshot()["tokens"] <= 10000
    assert Decimal(ledger.snapshot()["usd"]) <= Decimal("0.05")


def test_exact_token_ceiling_denies_without_consuming_request(tmp_path):
    ledger = AttemptLedger(tmp_path / "budget.sqlite3", limits())
    with pytest.raises(BudgetBlocked):
        ledger.reserve(payload("x" * 10000))
    assert ledger.snapshot()["requests"] == 0


def test_uncertain_attempt_denies_next_request_with_original_limits(tmp_path):
    ledger = AttemptLedger(tmp_path / "budget.sqlite3", limits())
    ledger.uncertain(ledger.reserve(payload()))
    with pytest.raises(BudgetBlocked):
        AttemptLedger(tmp_path / "budget.sqlite3", limits()).reserve(payload())
    assert ledger.snapshot()["requests"] == 1
