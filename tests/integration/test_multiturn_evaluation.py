import pytest

from eval.multiturn import Scenario, load_scenarios, run_scenarios


async def test_frozen_scenarios_have_reliable_oracles_and_honest_context_failure():
    scenarios, digest = load_scenarios()
    results = await run_scenarios(scenarios, dataset_sha256=digest)
    by_id = {r.case_id: r for r in results}
    assert by_id["cancel_confirm"].status == "PASS"
    assert by_id["cancel_replay"].status == "PASS"
    assert by_id["cross_user_session"].status == "PASS"
    assert by_id["context_loss"].status == "FAIL"
    assert "turn:1:missing_tool" in by_id["context_loss"].reasons
    assert all(r.model_evaluation == "NOT_RUN" for r in results)
    assert all(r.dataset_sha256 == digest for r in results)


async def test_malformed_case_and_missing_confirmation_cannot_be_success():
    with pytest.raises(Exception):
        Scenario.model_validate({"id": "bad", "turns": []})
    cases, digest = load_scenarios()
    case = next(c for c in cases if c.id == "cancel_confirm").model_copy(deep=True)
    case.turns[1].confirm = False
    results = await run_scenarios([case], dataset_sha256=digest)
    assert results[0].status == "FAIL"
    assert "wrong_final_status:ORD10003" in results[0].reasons
