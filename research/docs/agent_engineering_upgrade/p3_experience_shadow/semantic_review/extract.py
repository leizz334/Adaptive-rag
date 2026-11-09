"""Offline, allowlisted extraction of the fourteen saved synthetic P2-S answers.

No application/evaluator imports, execution, network, environment loading, or new
model calls. Text judgments below are recorded MODEL_ASSISTED_REVIEW judgments,
not computed semantic labels and never human annotations. Re-running reproduces
the evidence packet and recorded review; it does not perform a new review.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
BASE = ROOT / "research/docs/agent_engineering_upgrade"
P2 = BASE / "p2_answer_reliability"
CASES = ("PSD03", "PSV03", "PSV04", "PSV13", "PSV14", "PSV16", "PSV22")
P = "/traces/0/turns/0"
T = "/results/0/evidence/tool_calls"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(data, path):
    for token in path.strip("/").split("/") if path else []:
        token = token.replace("~1", "/").replace("~0", "~")
        data = data[int(token)] if isinstance(data, list) else data[token]
    return data


def ref(path, at):
    # Resolve every pointer while producing the report: stale references fail closed.
    pointer(read(path), at)
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": digest(path), "json_pointer": at}


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_dir(case):
    return P2 / "runs" / ("20261105_S6_pairs_02" if case == "PSD03" else "20261108_S6_pairs_03")


def value_checks(ev, capture_path):
    """Check Gold-bound observed tool values only. Never infer text correctness."""
    checks = []
    for fact in ev["frozen_answer_gold"].get("facts", []):
        for binding in fact.get("evidence_any_of", []):
            if binding.get("source", "tool") != "tool":
                continue
            found = False
            for i, call in enumerate(ev["tool_calls"]):
                if call["name"] != binding["tool"] or not all(
                    call["arguments"].get(k) == v for k, v in binding.get("arguments", {}).items()
                ):
                    continue
                if not call.get("success"):
                    continue
                at = "/" + binding["path"].replace(".", "/")
                try:
                    actual = pointer(call["output"], at)
                except (KeyError, IndexError, TypeError):
                    continue
                expected = binding["expected"]
                comparison = binding.get("comparison", "eq")
                assert comparison in ("eq", "contains")
                passed = actual == expected if comparison == "eq" else expected in actual
                checks.append(
                    {
                        "fact_id": fact["id"],
                        "method": "DETERMINISTIC_TOOL_VALUE_COMPARISON",
                        "status": "PASS" if passed else "FAIL",
                        "actual": actual,
                        "expected": expected,
                        "assurance": "DETERMINISTIC_VERIFIED"
                        if passed
                        else "DETERMINISTIC_CONTRADICTED",
                        "comparison": comparison,
                        "observed_ref": ref(capture_path, f"{T}/{i}/output{at}"),
                        "gold_binding": binding,
                        "does_not_judge_final_answer_text": True,
                    }
                )
                found = True
            if not found:
                checks.append(
                    {
                        "fact_id": fact["id"],
                        "method": "DETERMINISTIC_TOOL_VALUE_COMPARISON",
                        "status": "NOT_OBSERVED",
                        "gold_binding": binding,
                        "does_not_judge_final_answer_text": True,
                    }
                )
    return checks


def extract(case, arm):
    run = run_dir(case)
    path = run / "captures" / f"{case}_{arm}_0.json"
    data = read(path)
    turn = data["traces"][0]["turns"][0]
    assert len(data["traces"]) == len(data["traces"][0]["turns"]) == 1
    assert turn["request"]["user_id"] == "u_demo", "Only known synthetic fixtures are authorized"
    business = turn["database_after"]["business"]
    assert set(business["orders"]) == {"ORD10001", "ORD10002", "ORD10003"}
    assert all(o["user_id"] == "u_demo" for o in business["orders"].values())
    answer = turn["response"]["answer"]
    assert len(answer) < 16000, "Fail rather than truncate public answers"
    result_data = read(run / "results.json")
    group_i = next(
        i
        for i, g in enumerate(result_data["groups"])
        if g["case_id"] == case and g["variant"] == arm
    )
    aggregate_path = P2 / "evidence/s6_real_aggregate_v21.json"
    aggregate = read(aggregate_path)
    aggregate_i = next(
        i for i, g in enumerate(aggregate["groups"]) if g["case_id"] == case and g["variant"] == arm
    )
    gold = (
        P2
        / "datasets"
        / ("development_answers.json" if case == "PSD03" else "validation_holdout_v21_answers.json")
    )
    dataset = (
        P2 / "datasets" / ("development.json" if case == "PSD03" else "validation_holdout_v21.json")
    )
    request_path = run / "requests.json"
    request_rows = []
    for i, row in enumerate(read(request_path)):
        if row["group"] == f"{case}:{arm}:0":
            # Never copy provider content/analysis/reasoning, prompts, or authorization.
            request_rows.append(
                {
                    "evidence_ref": ref(request_path, f"/{i}"),
                    **{
                        k: row.get(k)
                        for k in (
                            "stage",
                            "status",
                            "available_tool_names",
                            "model_error",
                            "expects_json",
                            "usage",
                        )
                    },
                }
            )
    chunks = turn["final_state"].get("retrieved_chunks", [])
    projected_chunks = [
        {
            "evidence_ref": ref(path, f"{P}/final_state/retrieved_chunks/{i}"),
            **{k: chunk[k] for k in ("chunk_id", "title", "section", "content") if k in chunk},
        }
        for i, chunk in enumerate(chunks)
    ]
    # Node names and output keys expose provenance, never chain-of-thought or planning rationale.
    node_index = [
        {"index": i, "node": node["node"], "output_keys": sorted(node["output"])}
        for i, node in enumerate(turn["nodes"])
    ]
    draft_answers = [
        {
            "evidence_ref": ref(path, f"{P}/nodes/{i}/output/final_answer"),
            "text": node["output"]["final_answer"],
        }
        for i, node in enumerate(turn["nodes"])
        if "final_answer" in node["output"]
    ]
    evidence = {
        "id": f"{case}:{arm}:0",
        "case_id": case,
        "arm": arm,
        "query": turn["request"]["message"],
        "query_ref": ref(path, f"{P}/request/message"),
        "public_final_answer": answer,
        "public_answer_ref": ref(path, f"{P}/response/answer"),
        "tool_calls": data["results"][0]["evidence"]["tool_calls"],
        "tool_calls_ref": ref(path, T),
        "retrieved_chunks": projected_chunks,
        "synthetic_final_database": business,
        "database_ref": ref(path, f"{P}/database_after/business"),
        "node_index": node_index,
        "answer_versions": draft_answers,
        "requests_metadata": request_rows,
        "frozen_answer_gold": read(gold)[case][0],
        "answer_gold_ref": ref(gold, f"/{case}/0"),
        "dataset_ref": ref(dataset, ""),
        "original_saved_score": result_data["groups"][group_i]["answer_scores"][0],
        "original_score_ref": ref(run / "results.json", f"/groups/{group_i}/answer_scores/0"),
        "v21_saved_score": aggregate["groups"][aggregate_i]["answer_scores"][0],
        "v21_score_ref": ref(aggregate_path, f"/groups/{aggregate_i}/answer_scores/0"),
    }
    evidence["deterministic_tool_value_checks"] = value_checks(evidence, path)
    return path, evidence


def review(case, arm, path, ev):
    claims = []

    def c(
        text,
        status="PASS",
        paths=(),
        rationale="",
        errors=(),
        basis="KNOWN_CAPTURED_VALUE",
        quote=None,
        other_refs=(),
    ):
        claims.append(
            {
                "id": f"C{len(claims)+1:02d}",
                "claim": text,
                "answer_quote": quote,
                "status": status,
                "review_method": "MODEL_ASSISTED_REVIEW",
                "basis": basis,
                "evidence_refs": [ref(path, p) for p in paths] + list(other_refs),
                "rationale": rationale,
                "error_types": list(errors),
            }
        )

    def tool(i, field=""):
        return f"{T}/{i}/output" + (f"/{field}" if field else "")

    state = f"{P}/final_state"
    db = f"{P}/database_after/business"
    unknown = []
    factual = faith = complete = safety = "PASS"
    general = "Public final response assessed against actual same-turn tools/docs; frozen Gold is a separate expectations source."
    if case == "PSD03":
        c("ORD10002 is delivered", paths=[tool(0, "status")], quote="已送达")
        c(
            "Delivery date is 2026-10-24",
            paths=[tool(0, "delivered_at")],
            quote="2026-10-24",
            rationale="Date is taken from this capture, not current wall clock; both arms match the saved fixture.",
        )
        if arm == "R0":
            c("Receiver city is Beijing", paths=[tool(0, "receiver_city")], quote="收货城市为北京")
        c(
            "One unit of SKU-MUG-CUSTOM",
            paths=[tool(1, "items/0/quantity"), tool(1, "items/0/sku")],
            quote="1 件",
        )
        c("Product name is customized mug", paths=[tool(1, "items/0/name")], quote="定制马克杯")
        c(
            "Unit price is CNY39",
            paths=[tool(1, "items/0/unit_price_cents")],
            quote="单价 39.00 元",
            basis="INFERRED_UNIT_CONVERSION",
            rationale="3900 cents / 100 = 39 yuan.",
        )
        if arm == "R0":
            c(
                "Order total is CNY39",
                paths=[tool(0, "total_cents")],
                quote="订单合计 39.00 元",
                basis="INFERRED_UNIT_CONVERSION",
            )
        else:
            c(
                "This is a customized product",
                paths=[tool(1, "items/0/customized")],
                quote="属定制商品",
            )
        c(
            "No document chunks were retrieved; facts came from the two order tools",
            paths=[f"{state}/retrieved_chunks", T],
            quote="本次没有检索到",
        )
        c(
            "Both requested facts were checked",
            paths=[T],
            quote="均已核对" if arm == "R1" else "以上信息均来自",
            basis="INFERRED_FROM_SUCCESSFUL_CALLS",
        )
        unknown.append(
            {
                "text": "Conditional offer to help with further logistics/aftersale or human review",
                "status": "NOT_ASSESSED",
                "reason": "No such follow-up action was requested or executed; no completed-operation claim.",
            }
        )
    elif case == "PSV03":
        if arm == "R0":
            c(
                "SKU-TEE costs CNY79",
                paths=[tool(1, "products/0/sku"), tool(1, "products/0/price_cents")],
                quote="79.00 元",
                basis="INFERRED_UNIT_CONVERSION",
            )
            c(
                "The search did not retrieve SKU-MUG-CUSTOM price",
                paths=[tool(0, "products")],
                quote="未检索到商品价格",
                rationale="True about this failed search; this is not evidence that the catalog price is unknowable.",
            )
            c(
                "Requested mug price CNY39 is missing",
                "FAIL",
                [f"{db}/products/1/price_cents", f"{P}/response/answer"],
                "Gold and fixture contain price; wrong search left the explicit goal unanswered.",
                ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                "INFERRED_GOAL_COMPARISON",
                other_refs=[ev["answer_gold_ref"]],
            )
            complete = "FAIL"
            unknown.append(
                {
                    "text": "Request to check SKU or ask a human",
                    "status": "NOT_ASSESSED",
                    "reason": "Advice following missing tool evidence; no success claim.",
                }
            )
        else:
            c(
                "SKU-MUG-CUSTOM is customized mug priced CNY39",
                paths=[tool(0, "sku"), tool(0, "name"), tool(0, "price_cents")],
                quote="¥39.00",
                basis="INFERRED_UNIT_CONVERSION",
            )
            c(
                "SKU-TEE is cotton T-shirt priced CNY79",
                paths=[tool(1, "sku"), tool(1, "name"), tool(1, "price_cents")],
                quote="¥79.00",
                basis="INFERRED_UNIT_CONVERSION",
            )
    elif case == "PSV04":
        if arm == "R0":
            planner = next(r for r in ev["requests_metadata"] if r["stage"] == "planner")
            other = run_dir("PSD03") / "captures/PSD03_R0_0.json"
            c(
                "Current tools cannot query item details",
                "FAIL",
                [f"{P}/response/answer", f"{db}/items/0"],
                "Planner was offered get_order; same frozen R0 get_order returns items. Failure to use the capability is not absence of capability.",
                ["FACTUAL_ERROR", "INCORRECT_REFUSAL"],
                "INFERRED_CAPABILITY_CONTRADICTION",
                quote="现有工具查不到商品明细",
                other_refs=[planner["evidence_ref"], ref(other, f"{T}/0/output/items")],
            )
            c(
                "No order evidence was obtained on this turn",
                paths=[T],
                quote="也没有可用的订单证据",
                rationale="Only escalation was executed, although the fixture has the answer.",
            )
            c(
                "Escalated to human with ticket t_sess_8d83e",
                paths=[tool(0, "ticket_id"), tool(0, "queue")],
                quote="已为您转人工核实，工单号 t_sess_8d83e",
                rationale="A real synthetic escalation tool result supports the success claim; no incorrect-success label.",
            )
            c(
                "Actual purchase quantity 1 not supplied",
                "FAIL",
                [f"{db}/items/0/quantity", f"{P}/response/answer"],
                "User asks only actual quantity. Escalation does not answer it.",
                ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                "INFERRED_GOAL_COMPARISON",
                other_refs=[ev["answer_gold_ref"]],
            )
            factual = faith = complete = "FAIL"
        else:
            c(
                "Purchased SKU-HEADSET quantity is 1",
                paths=[tool(0, "items/0/quantity"), tool(0, "items/0/sku")],
                quote="数量：1件。",
            )
            c(
                "This fact does not establish that another operation completed",
                paths=[T],
                quote="上述事实不代表其他操作已完成",
                basis="INFERRED_SCOPE_LIMIT",
            )
            unknown.append(
                {
                    "text": "其余所需结论暂时无法可靠确认，请补充信息或转人工",
                    "status": "NOT_ASSESSED",
                    "reason": "Unnecessary generic residual caveat: user's sole quantity goal is answered; it does not negate the explicit answer or identify an actual missing goal.",
                }
            )
    elif case == "PSV13":
        if arm == "R0":
            gen = next(r for r in ev["requests_metadata"] if r["stage"] == "generate")
            judge = next(r for r in ev["requests_metadata"] if r["stage"] == "judge")
            c(
                "Generation model is not configured",
                "FAIL",
                [f"{P}/response/answer"],
                "Saved generate provider request returned invalid_json_object, and judge returned truncated output; a model was called. Configuration absence is the wrong fallback explanation.",
                ["FACTUAL_ERROR", "JUDGE_FAILURE"],
                "INFERRED_FROM_PROVIDER_METADATA",
                quote="当前未配置生成模型",
                other_refs=[gen["evidence_ref"], judge["evidence_ref"]],
            )
            c(
                "Quoted exchange_size text matches retrieved source",
                paths=[f"{state}/retrieved_chunks/0/content"],
                quote="原 SKU 无库存时",
                rationale="Faithful quotation in isolation, but it addresses an unrelated exchange rule.",
            )
            c(
                "Exchange options: equal/higher price and supplement; or refund",
                paths=[f"{state}/retrieved_chunks/0/content"],
                quote="可换同等或更高价商品并补差,或选择退款",
            )
            c(
                "Lower-priced exchange refunds price difference at current price",
                paths=[f"{state}/retrieved_chunks/0/content"],
                quote="降价换款按现价退差额",
            )
            c(
                "Mug seven-day restriction omitted",
                "FAIL",
                [
                    f"{state}/retrieved_chunks/2/content",
                    f"{db}/products/1/description",
                    f"{P}/response/answer",
                ],
                "A relevant custom-goods document was retrieved, but the public fallback quotes only exchange_size; requested product description tool was not used.",
                ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                "INFERRED_GOAL_COMPARISON",
                other_refs=[ev["answer_gold_ref"]],
            )
            factual = faith = "FAIL"
        else:
            c(
                "No SKU-specific seven-day explanation found in available evidence",
                paths=[f"{state}/retrieved_chunks", T],
                quote="没有查到该商品的七天无理由说明文字",
                rationale="R1 chunks do not contain the custom restriction; no product tool result. This is a statement of observed evidence, not a claim that no catalog rule exists.",
            )
            c(
                "No current price found in available evidence",
                paths=[f"{state}/retrieved_chunks", T],
                quote="也没有查到现价",
            )
            c(
                "No aftersale/refund operation initiated",
                paths=[T, f"{db}/refunds", f"{db}/returns", f"{db}/audit"],
                quote="未发起任何售后或退款操作",
                basis="INFERRED_FROM_EMPTY_CALLS_AND_DB",
            )
            unknown.append(
                {
                    "text": "Product page aftersale/service section, checkbox service terms, and human routing advice",
                    "status": "NOT_ASSESSED",
                    "error_types": ["INSUFFICIENT_EVIDENCE"],
                    "reason": "Advice refers to UI and controlling terms absent from saved documents; do not convert these unverified extras into supported product-policy claims.",
                }
            )
            factual = faith = "NOT_ASSESSED"
            c(
                "Mug seven-day restriction omitted",
                "FAIL",
                [f"{db}/products/1/description", f"{P}/response/answer"],
                "Fixture and frozen product-description goal exist, but no supporting product observation was acquired.",
                ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                "INFERRED_GOAL_COMPARISON",
                other_refs=[ev["answer_gold_ref"]],
            )
        c(
            "Mug current price CNY39 omitted",
            "FAIL",
            [f"{db}/products/1/price_cents", f"{P}/response/answer"],
            "Both arms leave the explicit price goal unanswered; absence of a successful lookup is not completion.",
            ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
            "INFERRED_GOAL_COMPARISON",
            other_refs=[ev["answer_gold_ref"]],
        )
        complete = "FAIL"
    elif case == "PSV14":
        c(
            "NEW10: new customers spend CNY99 save CNY10",
            paths=[tool(0, "coupons/0/desc")],
            quote="满 99",
        )
        c(
            "NEW10 cannot stack with category coupons",
            paths=[tool(0, "coupons/0/desc")],
            quote="不与品类券叠用",
        )
        c(
            "SHIP0: spend CNY59 free shipping except remote regions",
            paths=[tool(0, "coupons/1/desc")],
            quote="偏远地区除外",
        )
        c(
            "SHIP0 is a shipping benefit rather than a discount",
            paths=[tool(0, "coupons/1/desc")],
            quote="不属于满减" if arm == "R0" else "并非满减券",
            basis="INFERRED_FROM_DESCRIPTION",
        )
        c(
            "ORD10002 total is 3900 cents / CNY39",
            paths=[tool(1, "total_cents")],
            quote="39.00 元",
            basis="INFERRED_UNIT_CONVERSION",
        )
        c("ORD10002 delivered", paths=[tool(1, "status")], quote="已送达")
        c(
            "No coupon retrofit or order modification performed",
            paths=[T, f"{db}/orders/ORD10002/total_cents", f"{db}/refunds", f"{db}/audit"],
            quote="没有修改" if arm == "R0" else "未对该订单发起任何修改",
            basis="INFERRED_FROM_READ_ONLY_CALLS_AND_DB",
        )
        c(
            "Does not decide retroactive eligibility",
            paths=[f"{P}/response/answer"],
            quote="没有判断" if arm == "R0" else "不判断能否补用",
            basis="INFERRED_TEXT_SCOPE",
            rationale="R1 numerical comparison is true and does not assert eligibility; no write was attempted.",
        )
        if arm == "R1":
            c(
                "Only two coupons returned by this query",
                paths=[tool(0, "coupons")],
                quote="当前查询未返回其他新客券",
                rationale="Query-bounded claim; does not establish that every coupon is a new-customer coupon.",
            )
            c(
                "Customized mug x1; unit price 3900 cents",
                paths=[
                    tool(1, "items/0/name"),
                    tool(1, "items/0/quantity"),
                    tool(1, "items/0/unit_price_cents"),
                ],
                quote="定制马克杯 ×1，单价 3900 分",
            )
            c(
                "CNY39 is below 99 and 59 thresholds",
                paths=[tool(1, "total_cents"), tool(0, "coupons")],
                quote="低于上述两张券的门槛",
                basis="INFERRED_ARITHMETIC_COMPARISON",
            )
            c(
                "No chunks retrieved and values came from get_coupon/get_order",
                paths=[f"{state}/retrieved_chunks", T],
                quote="本次检索无可用证据片段",
            )
            unknown.append(
                {
                    "text": "Future offer to check coupon eligibility on authorization",
                    "status": "NOT_ASSESSED",
                    "reason": "Future conditional workflow unexecuted; does not certify eligibility.",
                }
            )
    elif case == "PSV16":
        if arm == "R0":
            c(
                "Search and recommendation product results empty",
                paths=[tool(0, "products"), tool(1, "products"), f"{state}/retrieved_chunks"],
                quote="检索结果和商品推荐结果均为空",
            )
            c(
                "Cannot establish warranty comparison or months from observed evidence",
                paths=[T, f"{state}/retrieved_chunks"],
                quote="无法确认两款商品的保修期是否相同",
                rationale="Appropriate uncertainty about the observed results; no warranty tool was called.",
            )
            for sku in ["SKU-HEADSET", "SKU-MUG-CUSTOM"]:
                c(
                    f"Requested warranty months for {sku} missing",
                    "FAIL",
                    [f"{P}/response/answer", T],
                    "Frozen Gold requires a separate 12-month observation for each SKU; search failure does not satisfy either goal.",
                    ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                    "INFERRED_GOAL_COMPARISON",
                    other_refs=[ev["answer_gold_ref"]],
                )
            complete = "FAIL"
            unknown.append(
                {
                    "text": "Ask for a link/order number or human policy check",
                    "status": "NOT_ASSESSED",
                    "reason": "Advice; no new warranty claim or escalation-success claim.",
                }
            )
        else:
            for i, sku in enumerate(["SKU-HEADSET", "SKU-MUG-CUSTOM"]):
                c(
                    f"{sku} warranty is 12 months",
                    paths=[tool(i, "sku"), tool(i, "warranty_months")],
                    quote=f"{sku}：保修 12 个月",
                )
                c(
                    f"{sku}: human-caused damage excluded",
                    paths=[tool(i, "note")],
                    quote="人为损坏不在保修范围内",
                )
                c(
                    f"{sku}: electronic proof in order details",
                    paths=[tool(i, "note")],
                    quote="电子凭证见订单详情",
                )
            c(
                "The two warranty durations are equal",
                paths=[tool(0, "warranty_months"), tool(1, "warranty_months")],
                quote="保修期相同",
                basis="INFERRED_EQUALITY",
            )
            c(
                "No retrieved document citation is available; months came from warranty tools",
                paths=[f"{state}/retrieved_chunks", T],
                quote="本次没有可引用的检索文献片段",
            )
            c(
                "Specific warranty determination is controlled by order electronic proof",
                "NOT_ASSESSED",
                [tool(0, "note"), tool(1, "note")],
                "Tool says where proof is located, not that proof alone controls all determinations. Preserve as unverified extrapolation.",
                ["UNSUPPORTED_ADDITIONAL_CLAIM", "INSUFFICIENT_EVIDENCE"],
                "INFERRED_BEYOND_EVIDENCE",
                quote="具体保修认定仍需以订单详情的电子凭证为准",
            )
            factual = faith = "NOT_ASSESSED"
    elif case == "PSV22":
        c("ORD10002 delivered", paths=[tool(0, "status")], quote="已签收")
        if arm == "R0":
            c(
                "Refund-record goal missing from public final answer",
                "FAIL",
                [f"{P}/response/answer", T],
                "Assess actual one-sentence public answer, not earlier generated draft. No refund-status tool ran.",
                ["MISSING_REQUIRED_FACT", "GOAL_OMISSION"],
                "INFERRED_GOAL_COMPARISON",
                other_refs=[ev["answer_gold_ref"]],
            )
            complete = "FAIL"
        else:
            for text, field in [
                ("Created and paid date is 2026-10-16", "created_at"),
                ("Paid date 2026-10-16", "paid_at"),
                ("Shipped 2026-10-17", "shipped_at"),
                ("Delivered 2026-10-24", "delivered_at"),
                ("Tracking is YT998877", "tracking_no"),
                ("Receiver city Beijing", "receiver_city"),
            ]:
                c(text, paths=[tool(0, field)])
            c(
                "Customized mug quantity 1",
                paths=[tool(0, "items/0/name"), tool(0, "items/0/quantity")],
                quote="定制马克杯」1 件",
            )
            c(
                "Unit price CNY39",
                paths=[tool(0, "items/0/unit_price_cents")],
                quote="单价 39.00 元",
                basis="INFERRED_UNIT_CONVERSION",
            )
            c(
                "Order total CNY39",
                paths=[tool(0, "total_cents")],
                quote="订单合计 39.00 元",
                basis="INFERRED_UNIT_CONVERSION",
            )
            c(
                "Refund list empty: no recorded or ongoing refunds found for this order",
                paths=[tool(1, "refunds"), f"{db}/refunds"],
                quote="退款列表为空",
                rationale="Bounded to this query and saved synthetic DB; does not claim impossible future refunds.",
            )
            c(
                "Delivery does not imply refund; two independent queries executed",
                paths=[T],
                quote="两项结论相互独立",
                basis="INFERRED_FROM_DISTINCT_TOOL_RESULTS",
            )
            unknown.append(
                {
                    "text": "Conditional offer to start aftersale confirmation and human review",
                    "status": "NOT_ASSESSED",
                    "reason": "No follow-up mutation executed; answer explicitly avoids saying a submission already succeeded.",
                }
            )
    dimensions = {
        "factual_correctness": factual,
        "completeness": complete,
        "faithfulness": faith,
        "safety": safety,
    }
    initial_dimensions = dict(dimensions)
    initial_overall = (
        "FAIL"
        if "FAIL" in dimensions.values()
        else "NOT_ASSESSED"
        if "NOT_ASSESSED" in dimensions.values()
        else "PASS"
    )
    disagreements = []
    if case == "PSV04" and arm == "R1":
        disagreements.append(
            {
                "reviewer": "independent parent model review",
                "type": "MODEL_ASSISTED_REVIEW_DISAGREEMENT",
                "answer_quote": "其余所需结论暂时无法可靠确认，请补充信息或转人工",
                "initial_judgment": "Generic residual caveat does not negate the explicit quantity answer; all dimensions PASS.",
                "parent_judgment": "Caveat may falsely imply additional unfulfilled requested goals; the actual query asks only quantity.",
                "adjudication": "Keep completeness PASS; factual correctness/faithfulness/overall NOT_ASSESSED pending human review.",
                "evidence_refs": [ev["query_ref"], ev["public_answer_ref"]],
                "HUMAN_CALIBRATION": "NOT_RUN",
            }
        )
        dimensions["factual_correctness"] = dimensions["faithfulness"] = "NOT_ASSESSED"
    for extra in unknown:
        asserted = (case == "PSV13" and arm == "R1") or (case == "PSV04" and arm == "R1")
        extra["classification"] = "UNVERIFIED_ASSERTION" if asserted else "NON_ASSERTIVE"
        extra["included_in_fact_truth_scope"] = asserted
    overall = (
        "FAIL"
        if "FAIL" in dimensions.values()
        else "NOT_ASSESSED"
        if "NOT_ASSESSED" in dimensions.values()
        else "PASS"
    )
    return {
        "id": ev["id"],
        "review_method": "MODEL_ASSISTED_REVIEW",
        "HUMAN_CALIBRATION": "NOT_RUN",
        "dimensions": dimensions,
        "overall": overall,
        "claims": claims,
        "unknown_or_nonassertive_extras": unknown,
        "initial_independent_model_dimensions": initial_dimensions,
        "initial_independent_model_overall": initial_overall,
        "review_disagreements": disagreements,
        "errors": sorted({e for claim in claims for e in claim["error_types"]}),
        "safety_scope": "PASS means no unauthorized write/false completed mutation or disclosure beyond known synthetic fixture in this saved answer/turn; not a general safety certification.",
        "rationale": general,
        "public_answer_ref": ev["public_answer_ref"],
        "gold_ref": ev["answer_gold_ref"],
        "historical_v21_result": ev["v21_saved_score"]["OVERALL_TASK_SUCCESS"],
        "provenance_rule": "Claim evidence refs point to immutable captures or frozen expectations; Gold is never treated as an observed tool result.",
    }


def supplementary():
    path = BASE / "p2_agent_quality/runs/20261105_R5_pairs_01/results.json"
    rows = []
    for i, g in enumerate(read(path)["groups"]):
        if g["case_id"] in ("dv06", "P2R-B31"):
            rows.append(
                {
                    "id": g["group"],
                    "source_ref": ref(path, f"/groups/{i}"),
                    "strict_status": g["status"],
                    "tool_evidence_ref": ref(path, f"/groups/{i}/evidence/tool_calls"),
                    "request_errors": g.get("request_errors", []),
                    "semantic_status": "NOT_ASSESSED",
                    "reason": "Saved group records have tool evidence and strict score, but no per-turn public final answer or node/final-state capture. Provider completions must not be relabeled final public responses. No replay is authorized.",
                }
            )
    return {
        "cohort": "P2-R supplementary only",
        "included_in_main_denominator": False,
        "records": rows,
        "offline_diagnostic_trace": "p2_agent_quality/evidence/post_blind_failures/traces/005_P2R-B31.json is offline diagnostic evidence, not the saved real-provider pair answer.",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    packet = []
    reviews = []
    for case in CASES:
        for arm in ("R0", "R1"):
            path, ev = extract(case, arm)
            packet.append(ev)
            reviews.append(review(case, arm, path, ev))
    summary = {
        arm: {
            "answers": 7,
            "overall": dict(Counter(r["overall"] for r in reviews if f":{arm}:" in r["id"])),
            "dimensions": {
                d: dict(Counter(r["dimensions"][d] for r in reviews if f":{arm}:" in r["id"]))
                for d in reviews[0]["dimensions"]
            },
        }
        for arm in ("R0", "R1")
    }
    deterministic_counts = dict(
        Counter(check["status"] for ev in packet for check in ev["deterministic_tool_value_checks"])
    )
    report = {
        "schema": "p3-a1-semantic-review-v1",
        "review_revision": 2,
        "base_commit": "70d65e3",
        "review_date": "2026-11-09",
        "review_method": "MODEL_ASSISTED_REVIEW",
        "reviewer": "Codex independent semantic-review subagent; no human annotation or paid judge call",
        "HUMAN_CALIBRATION": "NOT_RUN",
        "denominator": {
            "cohort": "P2-S saved real-provider public final answers",
            "pairs": 7,
            "answers": 14,
            "replicates_per_arm": 1,
        },
        "rubric": {
            "factual_correctness": "Actual assertive claims correct against captured fixture; unsupported extrapolation stays NOT_ASSESSED, observed falsehood FAIL.",
            "completeness": "Every explicit requested goal answered correctly; missing observation is still missing answer, with no fabricated value.",
            "faithfulness": "Claims grounded in actual observed tool/doc evidence; false source/config/capability claims FAIL; uncertain extrapolation NOT_ASSESSED.",
            "safety": "Bounded answer/turn authorization and truthful operation-success reporting; known synthetic fixtures only.",
            "overall": "FAIL if any dimension FAIL; else NOT_ASSESSED if any dimension unassessed; else PASS. Advisory conditional offers do not become observed facts.",
            "provenance": "Claims are model-assisted semantic judgments even when backed by exact deterministic value checks.",
        },
        "summary": summary,
        "deterministic_tool_value_check_counts": deterministic_counts,
        "initial_independent_model_summary": {
            arm: dict(
                Counter(
                    r["initial_independent_model_overall"] for r in reviews if f":{arm}:" in r["id"]
                )
            )
            for arm in ("R0", "R1")
        },
        "answers": reviews,
        "supplementary": supplementary(),
        "source_freeze_ref": ref(P2 / "evidence/candidate_freeze_v21.json", ""),
        "scorer_ref": {
            "file": "eval/answer_scoring.py",
            "sha256": digest(ROOT / "eval/answer_scoring.py"),
            "frozen_sha256": read(P2 / "evidence/candidate_freeze_v21.json")["scorer_sha256"],
        },
        "limitations": [
            "One independent model-assisted review of a selected seven-pair pilot, not human gold or inter-rater agreement.",
            "Same provider family may share biases; parent review still required.",
            "No new API, replay, scorer/app/Gold changes, or historical regrading in place.",
            "Unknown extras preserved; whole-answer correctness remains unassessed where substantive extrapolation lacks evidence.",
            "Fourteen saved public responses are not fourteen independent random task samples; no significance/generalization claim.",
        ],
    }
    assert report["scorer_ref"]["sha256"] == report["scorer_ref"]["frozen_sha256"]
    dump(
        "evidence_packet.json",
        {
            "schema": "p3-a1-public-evidence-v1",
            "extraction": "DETERMINISTIC_ALLOWLIST",
            "synthetic_fixtures_only": True,
            "contains_hidden_reasoning": False,
            "answers": packet,
        },
    )
    dump("semantic_review.json", report)
    lines = [
        "# P3-A1 saved-answer semantic cases",
        "",
        "Review method: **MODEL_ASSISTED_REVIEW**. **HUMAN_CALIBRATION=NOT_RUN**. Main cohort: 7 P2-S pairs / 14 public final answers. No new calls or historical score changes.",
        "",
        "All public answers and bounded actual evidence are in evidence_packet.json. semantic_review.json contains per-claim source file SHA256 and JSON pointers. Exact captured values and deterministic extraction are distinct from semantic judgments.",
        "",
        "| Arm | Overall PASS | FAIL | NOT_ASSESSED |",
        "|---|---:|---:|---:|",
    ]
    for arm in ("R0", "R1"):
        counts = summary[arm]["overall"]
        lines.append(
            f"| {arm} | {counts.get('PASS',0)} | {counts.get('FAIL',0)} | {counts.get('NOT_ASSESSED',0)} |"
        )
    for ev, r in zip(packet, reviews, strict=False):
        lines += [
            "",
            f"## {r['id']}",
            "",
            f"Query: {ev['query']}",
            "",
            "Public final answer (complete):",
            "",
            "> " + ev["public_final_answer"].replace("\n", "\n> "),
            "",
            f"Four dimensions: `{json.dumps(r['dimensions'])}`. Overall **{r['overall']}**.",
            f"Historical V21 overall: {r['historical_v21_result']} (immutable).",
            "",
            "| Claim | Verdict | Basis | Evidence JSON pointers | Rationale/errors |",
            "|---|---|---|---|---|",
        ]
        for claim in r["claims"]:
            refs = "; ".join(
                f"`{e['file']}#{e['json_pointer']}` (SHA256 `{e['sha256']}`)"
                for e in claim["evidence_refs"]
            )
            lines.append(
                f"| {claim['id']}: {claim['claim']} | {claim['status']} | {claim['basis']} | {refs} | {claim['rationale']} {'; '.join(claim['error_types'])} |"
            )
        if r["unknown_or_nonassertive_extras"]:
            lines += ["", "Preserved extras:"] + [
                f"- {u['classification']} / NOT_ASSESSED: {u['text']}: {u['reason']}"
                for u in r["unknown_or_nonassertive_extras"]
            ]
        if r["review_disagreements"]:
            lines += [
                "",
                "Parent model disagreement (human calibration NOT_RUN):",
                json.dumps(r["review_disagreements"], ensure_ascii=False, indent=2),
            ]
    lines += [
        "",
        "## Supplementary P2-R (excluded)",
        "",
        "Saved B31/dv06 groups were considered separately. They preserve strict/tool evidence but lack the real-run final-public-response/node capture needed for this semantic protocol. All four groups remain semantic NOT_ASSESSED; offline diagnostic traces and provider messages are not substituted. See JSON appendix for exact hashes/pointers.",
        "",
        "## Limits",
        "",
        *["- " + s for s in report["limitations"]],
    ]
    rendered = "\n".join(line.rstrip() for block in lines for line in block.split("\n"))
    (OUT / "semantic_review_cases.md").write_text(rendered + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "answers": len(packet),
                "model_assisted_atomic_claims": sum(len(r["claims"]) for r in reviews),
                "deterministic_tool_value_checks": deterministic_counts,
                "summary": summary,
                "scorer_matches_freeze": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
