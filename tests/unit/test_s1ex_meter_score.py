import pytest

from research.docs.agent_engineering_upgrade.s1_experience_optimization.meter import (
    Ledger,
    SafetyStop,
)
from research.docs.agent_engineering_upgrade.s1_experience_optimization.scoring import score


def test_budget_cannot_expand_and_unknown_dispatch_closes_admission(tmp_path):
    with pytest.raises(ValueError):
        Ledger(tmp_path / "invalid", limits={"requests": 121})
    ledger = Ledger(tmp_path / "valid")
    ledger.group = "case_E0"
    ledger.admit_triplet()
    ledger.admit(1000, 512)
    ledger.rows = [
        {
            "schema": "s1ex-request-v1",
            "status": "PENDING",
            "usage": None,
            "error": None,
            "group": "case_E0",
            "reserve_input": 1000,
            "reserve_output": 512,
        }
    ]
    with pytest.raises(SafetyStop):
        ledger.admit(1, 1)


def test_score_cannot_credit_negated_amount_missing_tool_or_write():
    task = {
        "orders": [{"order_id": "ORD77701"}],
        "required_tools": [{"name": "get_order", "arguments": {"order_id": "ORD77701"}}],
        "bounded_facts": [{"order": "ORD77701", "alternatives": ["12.34"]}],
    }
    calls = [{"name": "get_order", "arguments": {"order_id": "ORD77701"}, "success": True}]
    assert score(task, {"answer": "订单金额12.34元"}, calls, True)["bounded_e2e_proxy"] is True
    assert score(task, {"answer": "订单金额不是12.34元"}, calls, True)["bounded_e2e_proxy"] is False
    assert score(task, {"answer": "12.34元"}, [], True)["execution_success_proxy"] is False
    assert (
        score(task, {"answer": "12.34元"}, calls + [{"name": "cancel_order"}], False)[
            "execution_success_proxy"
        ]
        is False
    )
