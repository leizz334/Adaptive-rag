"""Evidence taxonomy contract: score-only/model hypotheses cannot prove causes."""

import importlib

import pytest
from pydantic import ValidationError


def modules():
    return importlib.import_module("app.experience.contracts"), importlib.import_module(
        "app.experience.taxonomy"
    )


def reference():
    return dict(artifact="traces/example.json", sha256="a" * 64, pointer="/turns/0", kind="trace")


def signal(category="ROUTING_ERROR", proof="TRACE_CONTRACT", position=2, **kw):
    return dict(
        category=category,
        proof=proof,
        node="route_complexity",
        position=position,
        evidence_refs=[reference()],
        summary="Observed required live evidence route absent",
        **kw,
    )


def classify(signals):
    _, engine = modules()
    return engine.classify_failure(
        source_trace_id="trace-abc",
        source_case_id="sample-a",
        source_version="1" * 40,
        signals=signals,
    )


def test_verified_failure_requires_trace_contract_evidence():
    value = classify([signal()])
    assert value.evidence_level == "VERIFIED_FAILURE"
    assert value.failure_type == "ROUTING_ERROR"
    assert value.first_error_node == "route_complexity"
    assert value.root_cause_status == "HYPOTHESIS"
    assert value.confidence_source == "TRACE_CONTRACT"


def test_score_only_cannot_infer_module_or_verify_failure():
    value = classify([signal(proof="SCORE_ONLY")])
    assert value.evidence_level == "UNDETERMINED"
    assert value.failure_type == "UNKNOWN"
    assert value.first_error_node is None


def test_model_hypothesis_is_likely_not_verified():
    value = classify([signal(proof="MODEL_REVIEW")])
    assert value.evidence_level == "LIKELY_FAILURE"
    assert value.root_cause_status == "HYPOTHESIS"
    assert value.confidence != "HIGH"


def test_earliest_confirmed_node_and_propagation_preserved():
    value = classify([signal("GOAL_OMISSION", position=9), signal(position=2)])
    assert value.first_error_node == "route_complexity"
    assert value.propagation == ["ROUTING_ERROR", "GOAL_OMISSION"]


def test_earlier_model_guess_does_not_replace_later_confirmed_error():
    value = classify(
        [
            signal("MEMORY_RESOLUTION_ERROR", proof="MODEL_REVIEW", position=1),
            signal("JUDGE_INVALID_OUTPUT", position=7),
        ]
    )
    assert value.failure_type == "JUDGE_INVALID_OUTPUT"
    assert "MEMORY_RESOLUTION_ERROR" in value.alternative_explanations


def test_scorer_artifact_is_not_agent_failure():
    value = classify([signal("EVALUATION_CONTRACT_ISSUE", proof="SCORER_ARTIFACT")])
    assert value.evidence_level == "EVALUATION_ARTIFACT"
    assert value.failure_type == "EVALUATION_CONTRACT_ISSUE"


def test_success_control_generates_no_failure_claim():
    value = classify([signal(proof="SUCCESS_CONTROL")])
    assert value.failure_type == "UNKNOWN"
    assert value.evidence_level == "UNDETERMINED"


def test_all_required_taxonomy_categories_are_supported():
    contracts, _ = modules()
    expected = set(
        "ROUTING_ERROR QUERY_REWRITE_ERROR RETRIEVAL_MISS RERANK_ERROR INSUFFICIENT_CONTEXT MEMORY_RESOLUTION_ERROR ENTITY_BINDING_ERROR PLANNER_TOOL_SELECTION_ERROR PLANNER_ARGUMENT_ERROR PLANNER_EXTRA_TOOL PLANNER_MISSING_TOOL TOOL_EXECUTION_ERROR STALE_BUSINESS_STATE GOAL_OMISSION ANSWER_FACTUAL_ERROR ANSWER_FAITHFULNESS_ERROR JUDGE_INVALID_OUTPUT JUDGE_API_ERROR FALLBACK_ERROR ENVIRONMENT_FAILURE EVALUATION_CONTRACT_ISSUE UNKNOWN".split()
    )
    assert {x.value for x in contracts.FailureType} == expected


def test_verified_signal_without_references_is_rejected():
    contracts, _ = modules()
    with pytest.raises(ValidationError):
        contracts.FailureSignal.model_validate(dict(signal(), evidence_refs=[]))


@pytest.mark.parametrize(
    "path", ["../secret.json", "D:/private.json", "https://outside.invalid/x", "/absolute.json"]
)
def test_evidence_reference_stays_relative(path):
    contracts, _ = modules()
    with pytest.raises(ValidationError):
        contracts.EvidenceRef.model_validate(dict(reference(), artifact=path))


def test_signal_limit_and_invalid_category_are_rejected():
    with pytest.raises((ValueError, ValidationError)):
        classify([signal()] * 65)
    with pytest.raises(ValidationError):
        classify([signal("MODEL_SELF_APPROVED")])
