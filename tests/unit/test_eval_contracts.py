import pytest
from pydantic import ValidationError

from eval.baseline import baseline_snapshot
from eval.contracts import EvaluationResult, ToolCall, TrajectorySpec


def test_reject_unknown_execution_and_result_states():
    with pytest.raises(ValidationError):
        ToolCall(name="get_order", status="sounds_successful")
    with pytest.raises(ValidationError):
        EvaluationResult(case_id="c", status="probably_passed")


def test_contract_preserves_actual_argument_and_equivalent_paths():
    event = ToolCall(name="get_order", arguments={"order_id": "ORD10001"}, success=False)
    assert ToolCall.model_validate_json(event.model_dump_json()).arguments == {"order_id": "ORD10001"}
    spec = TrajectorySpec(valid_paths=[["get_order"], ["get_order", "get_order_items"]])
    assert spec.valid_paths == [["get_order"], ["get_order", "get_order_items"]]


def test_baseline_is_offline_dataset_snapshot():
    result = baseline_snapshot()
    assert result["datasets"]["rag_eval.jsonl"]["rows"] == 65
    assert result["datasets"]["intent_100.jsonl"]["rows"] == 100
    assert result["datasets"]["e2e_eval.jsonl"]["rows"] == 16
    assert all(len(row["sha256"]) == 64 for row in result["datasets"].values())
    assert result["model_evaluation"] == "NOT_RUN"
