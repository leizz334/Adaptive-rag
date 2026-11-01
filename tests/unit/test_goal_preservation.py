from copy import deepcopy

from eval.contracts import EnvironmentExpectation
from eval.goal_scoring import score_goal


def test_preexisting_audit_and_application_deletion_or_modification_is_forbidden():
    initial = {
        "orders": {"a": {"status": "paid", "user_id": "a"}},
        "refunds": [{"refund_id": "r", "order_id": "a", "status": "requested"}],
        "returns": [],
        "audit": [{"id": 1, "action": "old", "payload": "a"}],
        "products": [],
        "items": [],
    }
    for key in ["refunds", "audit"]:
        actual = deepcopy(initial)
        actual[key] = []
        result = score_goal(
            initial, actual, EnvironmentExpectation(refunds=0 if key == "refunds" else 1), []
        )
        assert not result["success"]
