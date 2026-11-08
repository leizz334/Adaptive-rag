"""Independent synthetic review probes; no real data, credentials, or network."""

import importlib

import httpx
import pytest

from eval.answer_scoring import AnswerGold, EvidenceRequirement, FactAssertion, score_answer


def _gold():
    return AnswerGold(
        subgoals=["quantity"],
        semantic_required=False,
        facts=[
            FactAssertion(
                id="q",
                goal="quantity",
                subject="SKU-REVIEW-A",
                patterns=[r"1件"],
                evidence_any_of=[
                    EvidenceRequirement(
                        tool="get_order_items",
                        arguments={"order_id": "ORD8822"},
                        path="items.0.quantity",
                        expected=1,
                    )
                ],
            )
        ],
    )


def _score(answer, order_id="ORD8822"):
    return score_answer(
        answer=answer,
        gold=_gold(),
        tool_success=True,
        environment_success=True,
        calls=[
            dict(
                name="get_order_items",
                success=True,
                arguments={"order_id": "ORD8822"},
                output=dict(order_id=order_id, items=[dict(sku="SKU-REVIEW-A", quantity=1)]),
            )
        ],
    )


def test_unknown_extra_sku_quantity_is_not_a_verified_contradiction():
    result = _score("SKU-REVIEW-A 1件。SKU-REVIEW-B 1件。")
    assert result["OVERALL_TASK_SUCCESS"] == "NOT_ASSESSED", result


def test_foreign_response_order_cannot_support_requested_order_quantity():
    result = _score("SKU-REVIEW-A 1件。", order_id="ORD9933")
    assert result["facts"][0]["evidence"] is False, result
    assert result["OVERALL_TASK_SUCCESS"] != "PASS", result


@pytest.mark.asyncio
async def test_missing_usage_response_stops_the_next_dispatch(tmp_path):
    r = importlib.import_module(
        "research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs"
    )
    dispatches = []

    def reply(request):
        dispatches.append(request)
        return httpx.Response(
            200,
            json={
                "model": "synthetic",
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            },
        )

    ledger = r.Ledger(tmp_path)
    transport = r.Transport(
        ledger,
        "REVIEWONLY:R0:0",
        source_sha256="synthetic",
        config_sha256="synthetic",
        underlying=httpx.MockTransport(reply),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        body = dict(
            model="synthetic",
            messages=[dict(role="user", content="synthetic")],
            temperature=0,
            max_tokens=8,
        )
        await client.post("https://example.invalid/chat/completions", json=body)
        assert ledger.rows[0]["status"] == "RESPONSE" and ledger.rows[0]["usage"] is None
        with pytest.raises(r.SafetyStop):
            await client.post("https://example.invalid/chat/completions", json=body)
    assert len(dispatches) == 1


def test_eleven_completed_requests_copy_once_and_charge_10003_tokens(tmp_path):
    helpers = importlib.import_module(
        "research.docs.agent_engineering_upgrade.p2_answer_reliability.test_p2s_real_pairs"
    )
    r = importlib.import_module(
        "research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs"
    )
    parent, config, snapshots = helpers.ancestor.__wrapped__(r, tmp_path)
    probe = r.read(parent / "requests.json")[0]
    probe["usage"] = dict(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    rows = [probe] + [dict(
        probe, group=f"REVIEWCASE{i}:R0:0", sequence=0,
        usage=dict(prompt_tokens=900, completion_tokens=100, total_tokens=1000),
    ) for i in range(10)]
    result = r.read(parent / "results.json")
    result["groups"] = [dict(group=row["group"]) for row in rows[1:]]
    r.write(parent / "requests.json", rows)
    r.write(parent / "results.json", result)
    original = {p.name: p.read_bytes() for p in parent.iterdir() if p.is_file()}
    history, inherited, inherited_probe = r.inherit_budget(
        parent, snapshots=snapshots, roots=config["roots"],
        env_file=helpers.Path(config["env_file"]), pricing=config["pricing"],
    )
    assert inherited == rows and history["totals"]["http_attempts"] == 11
    assert history["totals"]["accounted_tokens"] == 10003
    assert inherited_probe["inherited_from"] == str(parent.resolve())
    child = tmp_path / "child"
    child.mkdir()
    r.write(child / "experiment_config.json", dict(history_ancestor=history))
    r.write(child / "requests.json", inherited)
    ledger = r.Ledger(child, pricing=config["pricing"])
    assert ledger.totals()["http_attempts"] == 11
    assert ledger.totals()["accounted_tokens"] == 10003
    for forecast in ((340, 0, 0), (0, 290000, 0), (0, 0, 3.0)):
        with pytest.raises(r.SafetyStop):
            ledger.forecast(*forecast)
    assert {p.name: p.read_bytes() for p in parent.iterdir() if p.is_file()} == original
