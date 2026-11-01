import pytest

from eval.contracts import ToolCall, ToolExpectation, TrajectorySpec
from eval.tool_scoring import score_tools


def spec():
    return TrajectorySpec(
        required=[ToolExpectation(name="get_order", arguments={"order_id": "ORD10001"})],
        allowed=["get_order", "get_order_items"],
        valid_paths=[["get_order"], ["get_order", "get_order_items"]],
        max_calls={"get_order": 1},
    )


@pytest.mark.parametrize(
    "calls,selection,args,valid,success,extra",
    [
        ([ToolCall(name="get_order", arguments={"order_id": "ORD10001"})], 1, 1, 1, 1, 0),
        ([ToolCall(name="get_order", arguments={"order_id": "ORD99999"})], 1, 0, 1, 1, 0),
        ([ToolCall(name="cancel_order", arguments={"order_id": "ORD10001"})], 0, 0, 0, 1, 1),
        ([], 0, 0, 0, None, 0),
        (
            [
                ToolCall(
                    name="get_order",
                    arguments={"order_id": "ORD10001"},
                    success=False,
                    failure_kind="dependency_error",
                )
            ],
            1,
            1,
            1,
            0,
            0,
        ),
        (
            [
                ToolCall(name="get_order", arguments={"order_id": "ORD10001"}),
                ToolCall(name="get_order_items"),
            ],
            1,
            1,
            1,
            1,
            0,
        ),
        (
            [
                ToolCall(name="get_order", arguments={"order_id": "ORD10001"}),
                ToolCall(name="get_order", arguments={"order_id": "ORD10001"}),
            ],
            1,
            1,
            0,
            1,
            1,
        ),
    ],
)
def test_actual_events_not_answer_keywords(calls, selection, args, valid, success, extra):
    result = score_tools(calls, spec())
    assert result["tool_selection_accuracy"] == selection
    assert result["tool_argument_accuracy"] == args
    assert result["trajectory_valid"] == valid
    assert result["tool_execution_success"] == success
    assert result["unnecessary_tool_calls"] == extra


def test_order_constraint_and_failure_classification():
    result = score_tools(
        [
            ToolCall(name="get_order_items", success=False, failure_kind="business_rejected"),
            ToolCall(name="get_order"),
        ],
        TrajectorySpec(
            allowed=["get_order", "get_order_items"], before=[("get_order", "get_order_items")]
        ),
    )
    assert result["trajectory_valid"] == 0
    assert result["failure_counts"] == {"business_rejected": 1}


def test_denial_not_execution_and_wrong_second_target_not_hidden_by_first():
    result = score_tools(
        [
            ToolCall(
                name="cancel_order",
                status="denied",
                success=False,
                failure_kind="permission_denied",
            )
        ],
        TrajectorySpec(required=[ToolExpectation(name="cancel_order")], allowed=["cancel_order"]),
    )
    assert result["tool_selection_accuracy"] == 0
    assert result["tool_execution_success"] is None
    result = score_tools(
        [
            ToolCall(name="get_order", arguments={"order_id": "ORD10001"}),
            ToolCall(name="get_order", arguments={"order_id": "ORD99999"}),
        ],
        spec(),
    )
    assert result["tool_argument_accuracy"] == 0.5


def test_no_required_tools_does_not_reward_irrelevant_call():
    result = score_tools([ToolCall(name="cancel_order")], TrajectorySpec())
    assert result["unnecessary_tool_calls"] == 1
    assert result["trajectory_valid"] == 0


def test_repeating_one_target_does_not_cover_two_distinct_required_targets():
    calls = [ToolCall(name="get_order", arguments={"order_id": "ORD10001"}) for _ in range(2)]
    result = score_tools(
        calls,
        TrajectorySpec(
            required=[
                ToolExpectation(name="get_order", arguments={"order_id": "ORD10001"}),
                ToolExpectation(name="get_order", arguments={"order_id": "ORD10002"}),
            ],
            allowed=["get_order"],
        ),
    )
    assert result["tool_argument_accuracy"] == 0.5
