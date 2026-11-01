from pathlib import Path

from eval.multiturn import load_scenarios, run_scenarios


def test_extended_eighty_cases_preserve_frozen_seed_and_have_unique_ids():
    seed, _ = load_scenarios()
    cases, _ = load_scenarios(Path("eval/dataset/agent_v2_extended.json"))
    assert len(cases) == 80
    assert len({c.id for c in cases}) == 80
    assert [c.model_dump() for c in cases[:14]] == [c.model_dump() for c in seed]
    assert len({c.family for c in cases}) >= 11


async def test_explicit_query_observes_changed_business_state_without_memory_change():
    cases, digest = load_scenarios(Path("eval/dataset/agent_v2_extended.json"))
    selected = [c for c in cases if c.id == "freshness_ORD10001_explicit_changed"]
    assert len(selected) == 1
    results = await run_scenarios(selected, dataset_sha256=digest)
    assert results[0].status == "PASS", results[0].reasons
    assert results[0].evidence["actual_order_states"]["ORD10001"] == "delivered"
