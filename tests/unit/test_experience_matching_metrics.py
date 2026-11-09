"""Hand-calculated metric contract, independent of matcher predictions."""

from research.docs.agent_engineering_upgrade.p3_experience_validation.evaluate_matching import (
    summarize,
)


def test_precision_and_recall_use_distinct_false_positive_and_negative_denominators():
    rows = [
        dict(match=True, expected=True, safety_conflict=False, missing_guards=[]),
        dict(match=True, expected=False, safety_conflict=True, missing_guards=["KEEP_OWNER"]),
        dict(match=False, expected=True, safety_conflict=False, missing_guards=[]),
        dict(match=False, expected=False, safety_conflict=False, missing_guards=[]),
    ]
    metrics = summarize(rows)
    assert (metrics["TP"], metrics["FP"], metrics["FN"], metrics["TN"]) == (1, 1, 1, 1)
    assert metrics["precision"] == 0.5 and metrics["recall"] == 0.5
    assert metrics["safety_conflicts"] == 1 and metrics["missing_required_guard_decisions"] == 1
    assert metrics["strict_validation_pass"] is False


def test_no_positives_is_not_reported_as_perfect_precision_or_recall():
    metrics = summarize(
        [dict(match=False, expected=False, safety_conflict=False, missing_guards=[])]
    )
    assert metrics["precision"] is None and metrics["recall"] is None
