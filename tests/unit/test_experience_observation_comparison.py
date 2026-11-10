import importlib


def api():
    return importlib.import_module(
        "research.docs.agent_engineering_upgrade.p3_experience_validation.analyze_run"
    )


def test_only_well_formed_pending_confirmation_handles_are_nondeterministic():
    a = dict(decisions=[dict(pending=dict(action_id="act_" + "a" * 32, order_id="ORD10003"))])
    b = dict(decisions=[dict(pending=dict(action_id="act_" + "b" * 32, order_id="ORD10003"))])
    result = api().compare_behavior(a, b)
    assert result["raw_equal"] is False and result["decision_equal"] is True
    assert len(result["fresh_handle_differences"]) == 1
    b["decisions"][0]["pending"]["order_id"] = "ORD10001"
    assert api().compare_behavior(a, b)["decision_equal"] is False


def test_changed_answer_permission_or_malformed_handle_is_never_normalized():
    a = dict(
        decisions=[
            dict(pending=dict(action_id="act_" + "a" * 32), answer="pending", confirmed=False)
        ]
    )
    b = dict(
        decisions=[
            dict(
                pending=dict(action_id="not-a-valid-generated-handle"),
                answer="pending",
                confirmed=False,
            )
        ]
    )
    assert api().compare_behavior(a, b)["decision_equal"] is False
    b = dict(
        decisions=[dict(pending=dict(action_id="act_" + "b" * 32), answer="done", confirmed=True)]
    )
    assert api().compare_behavior(a, b)["decision_equal"] is False
