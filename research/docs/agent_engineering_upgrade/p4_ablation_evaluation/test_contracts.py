import json

import httpx
import pytest

from research.docs.agent_engineering_upgrade.p4_ablation_evaluation.meter import (
    Ledger,
    MeteredTransport,
    SafetyStop,
)
from research.docs.agent_engineering_upgrade.p4_ablation_evaluation.scoring import (
    score,
    transitions,
)


def test_d_budget_namespace_and_complete_pair_admission(tmp_path):
    ledger = Ledger(tmp_path)
    ledger.admit_pair(4)
    ledger.rows = [
        dict(
            schema="p4d-request-v1",
            group="old",
            status="RESPONSE",
            usage=dict(prompt_tokens=120000, completion_tokens=1, total_tokens=120001),
            reserve_input=120000,
            reserve_output=1,
            error=None,
        )
    ]
    with pytest.raises(SafetyStop):
        ledger.admit_pair(4)
    with pytest.raises(ValueError):
        Ledger(tmp_path, limits=dict(requests=181))


async def test_d_transport_keeps_new_namespace_and_writeahead(tmp_path):
    ledger = Ledger(tmp_path)

    def upstream(request):
        assert json.loads(ledger.path.read_text())[0]["schema"] == "p4d-request-v1"
        return httpx.Response(
            200,
            json=dict(
                model="deepseek-flash",
                choices=[dict(message=dict(content="{}"), finish_reason="stop")],
                usage=dict(prompt_tokens=8, completion_tokens=4, total_tokens=12),
            ),
        )

    async with httpx.AsyncClient(
        transport=MeteredTransport(ledger, httpx.MockTransport(upstream))
    ) as client:
        await client.post(
            "https://api.deepseek.com/chat/completions",
            json=dict(
                model="deepseek-flash",
                messages=[dict(role="user", content="synthetic")],
                max_tokens=16,
            ),
        )
    assert Ledger(tmp_path).totals()["http_attempts"] == 1
    ledger.rows[0]["status"] = "PENDING"
    ledger.save()
    with pytest.raises(SafetyStop):
        Ledger(tmp_path).admit_pair(3)


def test_negated_money_and_wrong_entity_do_not_pass():
    case = dict(kind="memory", order="ORD93041", cents=23780)
    state = dict(
        orders=[dict(order_id="ORD93041", status="paid")], audit_logs=[], idempotency_keys=[]
    )
    row = dict(
        status=200,
        body=dict(answer="总金额不是237.80元"),
        tools=[dict(name="get_order", success=True, arguments=dict(order_id="ORD93041"))],
        before=state,
        after=state,
    )
    assert not score(case, row)["objective_success"]
    row["body"]["answer"] = "总金额237.80元"
    assert score(case, row)["objective_success"]
    row["tools"][0]["arguments"]["order_id"] = "ORD00000"
    assert not score(case, row)["objective_success"]


def test_incomplete_pairs_never_form_effect_denominators():
    assert (
        transitions([dict(complete=False, arms={"M0": False, "M1": True})], "M0", "M1")[
            "valid_pairs"
        ]
        == 0
    )
    result = transitions([dict(complete=True, arms={"M0": True, "M1": False})], "M0", "M1")
    assert result["negative"] == 1 and result["positive"] == 0


def test_policy_duration_negation_and_wrong_citation_fail_closed():
    case = dict(kind="rag", relevant_ids=["D_R04"], atoms=[["240天"], ["订单凭证"]], forbidden=[])
    state = dict(orders=[], audit_logs=[], idempotency_keys=[])
    row = dict(
        status=200,
        body=dict(answer="保修不是240天，需要订单凭证。", citations=[dict(document_id="D_R04")]),
        tools=[],
        before=state,
        after=state,
    )
    assert not score(case, row)["objective_success"]
    row["body"]["answer"] = "保修240天，需要订单凭证。"
    assert score(case, row)["objective_success"]
    row["body"]["citations"] = [dict(document_id="D_R01")]
    assert not score(case, row)["objective_success"]


@pytest.mark.parametrize(
    "qid,answer",
    [
        ("D_Q01", "14天内退货，无需未使用，也无需包装和配件。不能保证服务，已烧水照样可以退货。"),
        ("D_Q02", "保修240天，单侧无声可免费维修，需订单凭证。进水也免费维修；不能保证当天完成。"),
    ],
)
def test_independent_review_policy_contradictions_never_pass(qid, answer):
    from research.docs.agent_engineering_upgrade.p4_ablation_evaluation.common import HERE

    cases = json.loads((HERE / "tasks.json").read_text())["cases"]
    case = next(c for c in cases if c["id"] == qid)
    state = dict(orders=[], audit_logs=[], idempotency_keys=[])
    row = dict(
        status=200,
        body=dict(answer=answer, citations=[dict(document_id=case["relevant_ids"][0])]),
        tools=[],
        before=state,
        after=state,
    )
    assert score(case, row)["objective_success"] is not True


def test_unassessed_semantic_arm_excludes_effect_pair():
    assert (
        transitions([dict(complete=True, arms={"BM25": None, "DENSE": True})], "BM25", "DENSE")[
            "valid_pairs"
        ]
        == 0
    )


@pytest.mark.parametrize("qid", ["D_Q01", "D_Q02"])
def test_canonical_source_policy_supported_but_incomplete_paraphrase_abstains(qid):
    from research.docs.agent_engineering_upgrade.p4_ablation_evaluation.common import HERE

    case = next(c for c in json.loads((HERE / "tasks.json").read_text())["cases"] if c["id"] == qid)
    doc = next(
        c
        for c in json.loads((HERE / "corpus.json").read_text())["documents"]
        if c["id"] in case["relevant_ids"]
    )
    state = dict(orders=[], audit_logs=[], idempotency_keys=[])
    row = dict(
        status=200,
        body=dict(answer=doc["content"], citations=[dict(document_id=case["relevant_ids"][0])]),
        tools=[],
        before=state,
        after=state,
    )
    assert score(case, row)["objective_success"] is True
    row["body"]["answer"] = "14天" if qid == "D_Q01" else "240天"
    assert score(case, row)["objective_success"] is None
