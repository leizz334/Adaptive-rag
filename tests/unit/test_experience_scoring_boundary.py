import importlib

import pytest

from eval.multiturn import Scenario


@pytest.mark.parametrize(
    "field,value",
    [
        ("message", "cancel now"),
        ("user_id", "another-owner"),
        ("confirm", True),
        ("state_changes", {"ORD10001": "cancelled"}),
    ],
)
def test_gold_cannot_change_actual_request_or_business_action(field, value):
    api = importlib.import_module(
        "research.docs.agent_engineering_upgrade.p3_experience_validation.run_experiment"
    )
    case = Scenario(
        id="boundary", family="boundary", user_goal="你好", turns=[dict(message="你好")]
    )
    with pytest.raises(ValueError):
        api.scoring_case(case, dict(expected={}, turns=[{field: value}]))


def test_scoring_case_keeps_user_request_and_only_adds_oracles():
    api = importlib.import_module(
        "research.docs.agent_engineering_upgrade.p3_experience_validation.run_experiment"
    )
    case = Scenario(
        id="boundary", family="boundary", user_goal="你好", turns=[dict(message="你好")]
    )
    scored = api.scoring_case(
        case, dict(expected={}, turns=[dict(trajectory=dict(required=[]), expected_pending=False)])
    )
    assert scored.turns[0].message == "你好"
    assert scored.turns[0].expected_pending is False
