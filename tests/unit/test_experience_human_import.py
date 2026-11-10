import copy
import importlib

import pytest

from research.docs.agent_engineering_upgrade.p3_experience_validation import (
    prepare_human_review as p,
)


def api():
    return importlib.import_module(
        "research.docs.agent_engineering_upgrade.p3_experience_validation.human_import"
    )


def rows():
    cases, _, _ = p.load_verified_cases()
    return [
        dict(
            case_id=c["case_id"],
            answer_sha256=p.sha_text(c["public_final_answer"]),
            query_sha256=p.sha_text(c["query"]),
            factual_correctness="PASS",
            completeness="PASS",
            faithfulness="PASS",
            safety="PASS",
            overall_verdict="PASS",
            reviewer_name="",
            reviewed_at="",
            notes="",
        )
        for c in cases
    ]


def test_attested_review_preserves_uncertainty_and_unknown_metadata():
    data = rows()
    data[2].update(factual_correctness="UNCERTAIN", overall_verdict="UNCERTAIN")
    result = api().validate_rows(data, attested_by_user=True)
    assert result["overall_counts"] == {"PASS": 6, "FAIL": 0, "UNCERTAIN": 1}
    assert result["calibration_status"] == "PARTIAL"
    assert result["experience_approval"] is False
    assert result["missing_reviewer_rows"] == 7
    assert result["missing_review_time_rows"] == 7
    assert result["rows"] == data


@pytest.mark.parametrize(
    "mutation",
    ["hash", "duplicate", "missing", "enum", "aggregate", "extra", "formula", "timestamp"],
)
def test_reject_corrupt_or_inconsistent_human_submission(mutation):
    data = copy.deepcopy(rows())
    if mutation == "hash":
        data[0]["answer_sha256"] = "0" * 64
    if mutation == "duplicate":
        data[1] = data[0].copy()
    if mutation == "missing":
        data.pop()
    if mutation == "enum":
        data[0]["safety"] = "NOT_ASSESSED"
    if mutation == "aggregate":
        data[0]["completeness"] = "FAIL"
    if mutation == "extra":
        data[0]["unexpected"] = "PASS"
    if mutation == "formula":
        data[0]["notes"] = "=HYPERLINK(bad)"
    if mutation == "timestamp":
        data[0]["reviewed_at"] = "yesterday"
    with pytest.raises(ValueError):
        api().validate_rows(data, attested_by_user=True)


def test_human_status_cannot_be_fabricated_without_user_attestation():
    with pytest.raises(ValueError):
        api().validate_rows(rows(), attested_by_user=False)
