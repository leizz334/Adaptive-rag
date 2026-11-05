"""Versioned Chinese development tasks and independent answer-only counterexamples."""

import copy
import re

from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import HERE, save

SAFE_EXTRA = [
    "以下是本次工具结果可确认的信息",
    "其余所需结论暂时无法可靠确认，请补充信息或转人工",
    "上述事实不代表其他操作已完成",
    "人民币",
    "当前订单状态",
    "订单状态",
    "总金额",
    "的物流状态",
    "物流状态",
    "订单商品",
    "订单",
    "商品",
    "数量",
    "库存",
    "价格",
    "保修期",
    "名称",
    "资料",
    "工具原文",
    r"['\"]",
]


def evidence(tool, args, path, value):
    return dict(tool=tool, arguments=args, path=path, expected=value)


def fact(kind, subject, tool, args, path, value, patterns, *, required=True):
    return dict(
        id=kind + "_" + subject,
        goal=kind,
        subject=subject,
        patterns=patterns,
        evidence_any_of=[evidence(tool, args, path, value)],
        required=required,
    )


def header(oid, status, amount, *, money_required=False):
    label = {"shipped": "已发货", "delivered": "已签收", "paid": "已支付", "cancelled": "已取消"}[
        status
    ]
    args = dict(order_id=oid)
    primary = "订单状态:" + oid
    return [
        fact(primary, oid, "get_order", args, "status", status, [label, status]),
        dict(
            fact(
                "总额",
                oid,
                "get_order",
                args,
                "total_cents",
                amount,
                [rf"{amount/100:.2f}\s*元"],
                required=money_required,
            ),
            goal=("订单金额:" + oid) if money_required else primary,
        ),
    ]


def shipment(oid, status):
    label = {"in_transit": "运输中", "delivered": "已签收", "warehouse": "仓库处理中"}[status]
    index = {"warehouse": 0, "in_transit": 1, "delivered": 2}[status]
    return fact(
        "物流",
        oid,
        "track_shipment",
        dict(order_id=oid),
        f"events.{index}.status",
        status,
        [label, status],
    )


def inventory(sku, number, tool="check_inventory", *, required=True, goal="库存"):
    return fact(
        goal, sku, tool, dict(sku=sku), "inventory", number, [rf"{number}\s*件"], required=required
    )


def product(sku, price, stock, name, description):
    args = dict(sku=sku)
    return [
        fact(
            "商品价格",
            sku,
            "get_product_detail",
            args,
            "price_cents",
            price,
            [rf"{price/100:.2f}\s*元"],
        ),
        inventory(sku, stock, "get_product_detail"),
        fact("商品名称", sku, "get_product_detail", args, "name", name, [re.escape(name)]),
        fact(
            "商品资料",
            sku,
            "get_product_detail",
            args,
            "description",
            description,
            [re.escape(description)],
        ),
    ]


def gold(facts, *, semantic=False, abstention=False, forbidden=None):
    return dict(
        schema_version="answer-eval-v2.0",
        subgoals=list(dict.fromkeys(f["goal"] for f in facts if f.get("required", True)))
        or ["开放语义"],
        facts=facts,
        forbidden_patterns=forbidden or ["当前未配置生成模型", r"退款成功", r"款项已到账"],
        allowed_extra_patterns=SAFE_EXTRA,
        expected_abstention=abstention,
        semantic_required=semantic,
    )


def need(tool, **args):
    return dict(name=tool, arguments=args)


def turn(message, required=(), allowed=(), **kw):
    return dict(
        message=message,
        trajectory=dict(
            required=list(required),
            allowed=list(allowed),
            max_calls={n: 1 for n in {r["name"] for r in required} | set(allowed)},
        ),
        **kw,
    )


def build():
    cases = []
    answers = {}

    def add(
        identifier, query, required, facts, *, allowed=(), expected=None, semantic=False, **turn_kw
    ):
        cases.append(
            dict(
                id=identifier,
                family="answer_" + identifier,
                user_goal=query,
                turns=[turn(query, required, allowed, **turn_kw)],
                expected=expected or {},
            )
        )
        answers[identifier] = [gold(facts, semantic=semantic)]

    add(
        "PSD01",
        "请把 ORD10001 当前订单状态和订单总金额一起核实给我。",
        [need("get_order", order_id="ORD10001")],
        header("ORD10001", "shipped", 29900, money_required=True),
    )
    add(
        "PSD02",
        "帮我读一下 ORD10002 目前最后一条物流状态。",
        [need("track_shipment", order_id="ORD10002")],
        [shipment("ORD10002", "delivered")],
    )
    items = fact(
        "商品件数",
        "SKU-MUG-CUSTOM",
        "get_order_items",
        dict(order_id="ORD10002"),
        "items.0.quantity",
        1,
        [r"(?:数量[：:]?)?1\s*件"],
    )
    add(
        "PSD03",
        "我需要 ORD10002 的订单阶段和商品数量，两项都写清楚。",
        [need("get_order", order_id="ORD10002"), need("get_order_items", order_id="ORD10002")],
        header("ORD10002", "delivered", 3900) + [items],
    )
    add(
        "PSD04",
        "ORD10003 不用列快递，只查订单目前状态以及总额。",
        [need("get_order", order_id="ORD10003")],
        header("ORD10003", "paid", 7900, money_required=True),
    )
    add(
        "PSD05",
        "ORD10001 的物流情况和订单总金额分开列出来，别漏掉钱数。",
        [need("get_order", order_id="ORD10001"), need("track_shipment", order_id="ORD10001")],
        header("ORD10001", "shipped", 29900, money_required=True)
        + [shipment("ORD10001", "in_transit")],
    )
    add(
        "PSD06",
        "请比较 ORD10001、ORD10003 两笔订单的当前状态。",
        [need("get_order", order_id="ORD10001"), need("get_order", order_id="ORD10003")],
        header("ORD10001", "shipped", 29900) + header("ORD10003", "paid", 7900),
    )
    add(
        "PSD07",
        "SKU-TEE 库存现在是多少件，别替我下单。",
        [need("check_inventory", sku="SKU-TEE")],
        [inventory("SKU-TEE", 0)],
    )
    add(
        "PSD08",
        "SKU-HEADSET 价格、库存、名称和详细资料都请查询后列给我。",
        [need("get_product_detail", sku="SKU-HEADSET")],
        product("SKU-HEADSET", 29900, 42, "降噪耳机 Pro", "头戴式主动降噪耳机"),
    )
    add(
        "PSD09",
        "SKU-MUG-CUSTOM 的单价、库存、名称和商品资料是什么？",
        [need("get_product_detail", sku="SKU-MUG-CUSTOM")],
        product(
            "SKU-MUG-CUSTOM", 3900, 200, "定制马克杯", "支持印字的定制杯，定制商品不适用7天无理由"
        ),
    )
    warranty = [
        fact(
            "保修期",
            "SKU-HEADSET",
            "get_warranty",
            dict(sku="SKU-HEADSET"),
            "warranty_months",
            12,
            [r"12\s*个?月"],
        ),
        fact(
            "保修排除",
            "SKU-HEADSET",
            "get_warranty",
            dict(sku="SKU-HEADSET"),
            "note",
            "人为损坏不在保，电子凭证见订单详情",
            ["人为损坏不在保", "人为损坏不属于保修"],
        ),
    ]
    add(
        "PSD10",
        "查 SKU-HEADSET 保修有几个月，并确认人为损坏是否在保。",
        [need("get_warranty", sku="SKU-HEADSET")],
        warranty,
    )
    add(
        "PSD11",
        "ORD10002 目前有没有退款记录，请看已有退款单而不是申请新退款。",
        [need("get_refund_status", order_id="ORD10002")],
        [
            fact(
                "退款记录",
                "",
                "get_refund_status",
                dict(order_id="ORD10002"),
                "refunds",
                [],
                ["暂未发现退款申请记录", "没有退款记录", "暂无退款记录"],
            )
        ],
    )
    add(
        "PSD12",
        "只查 ORD10001 买的商品各有几件，不要发起售后。",
        [need("get_order_items", order_id="ORD10001")],
        [
            fact(
                "商品件数",
                "SKU-HEADSET",
                "get_order_items",
                dict(order_id="ORD10001"),
                "items.0.quantity",
                1,
                [r"(?:数量[：:]?)?1\s*件"],
            )
        ],
    )
    add(
        "PSD13",
        "取消 ORD10003 之前先让我核对确认信息。",
        [],
        [],
        allowed=["get_order"],
        expected_pending=True,
        semantic=True,
    )
    add(
        "PSD14",
        "ORD10001 已发货了，帮我取消这单。",
        [],
        [],
        allowed=["get_order"],
        expected_pending=True,
        semantic=True,
    )
    cases[-1]["turns"].append(
        turn(
            "确认取消上述订单。",
            [need("cancel_order", order_id="ORD10001")],
            ["get_order"],
            confirm=True,
            expected_pending=False,
            expected_failures=["business_rejected"],
        )
    )
    answers["PSD14"].append(gold([], semantic=True))
    add(
        "PSD15",
        "直接取消 ORD10003 这笔未发货订单。",
        [],
        [],
        allowed=["get_order"],
        expected_pending=True,
        semantic=True,
    )
    cases[-1]["turns"].append(
        turn(
            "确认取消，请执行并告诉我是否完成。",
            [need("cancel_order", order_id="ORD10003")],
            ["get_order"],
            confirm=True,
            expected_pending=False,
        )
    )
    cases[-1]["expected"] = dict(
        orders=dict(ORD10003="cancelled"),
        allowed_mutations=["ORD10003"],
        audit_actions=["cancel_order"],
    )
    answers["PSD15"].append(
        gold(
            [
                fact(
                    "取消结果",
                    "ORD10003",
                    "cancel_order",
                    dict(order_id="ORD10003"),
                    "status",
                    "cancelled",
                    ["已取消", "取消成功"],
                )
            ],
            forbidden=[r"退款成功", r"款项已到账"],
        )
    )
    add(
        "PSD16",
        "我不是这笔单的用户，请查 ORD10001 的订单状态。",
        [need("get_order", order_id="ORD10001")],
        [],
        expected_failures=["business_rejected"],
        semantic=True,
    )
    cases[-1]["user_id"] = "other_test_user"
    add("PSD17", "讲一下定制商品一般的退货政策，不查询我的订单。", [], [], semantic=True)
    add(
        "PSD18",
        "ORD10001 的快递现在怎么样，另外解释配送时效政策。",
        [need("track_shipment", order_id="ORD10001")],
        [shipment("ORD10001", "in_transit")],
        allowed=["search_knowledge"],
        semantic=True,
    )
    add("PSD19", "你好！", [], [], semantic=True)
    add(
        "PSD20",
        "SKU-TEE 库存超过十件才取消 ORD10003，不满足条件不要操作。",
        [need("check_inventory", sku="SKU-TEE")],
        [inventory("SKU-TEE", 0)],
        expected_pending=False,
        semantic=True,
    )
    add(
        "PSD21",
        "查看 SKU-UNAVAILABLE 的详细资料与价格。",
        [need("get_product_detail", sku="SKU-UNAVAILABLE")],
        [],
        expected_failures=["business_rejected"],
        semantic=True,
    )
    cases[-1]["turns"].append(
        turn(
            "编号应为 SKU-HEADSET，请查这个的价格、库存、名称及详细资料。",
            [need("get_product_detail", sku="SKU-HEADSET")],
        )
    )
    answers["PSD21"].append(
        gold(product("SKU-HEADSET", 29900, 42, "降噪耳机 Pro", "头戴式主动降噪耳机"))
    )
    add(
        "PSD22",
        "先核实 ORD10003 的订单状态与订单总额。",
        [need("get_order", order_id="ORD10003")],
        header("ORD10003", "paid", 7900, money_required=True),
    )
    cases[-1]["turns"].append(
        turn(
            "现在重新查刚才那笔订单的状态和总额，使用最新记录。",
            [need("get_order", order_id="ORD10003")],
            state_changes=dict(ORD10003="cancelled"),
        )
    )
    cases[-1]["expected"] = dict(orders=dict(ORD10003="cancelled"), allowed_mutations=["ORD10003"])
    answers["PSD22"].append(gold(header("ORD10003", "cancelled", 7900, money_required=True)))
    add(
        "PSD23",
        "先看 ORD10001 的订单状态和金额。",
        [need("get_order", order_id="ORD10001")],
        header("ORD10001", "shipped", 29900, money_required=True),
    )
    cases[-1]["turns"].append(turn("新会话里查那笔订单的状态。", [], new_session=True))
    answers["PSD23"].append(gold([], semantic=True, abstention=True))
    add(
        "PSD24",
        "先把 ORD10003 的订单阶段和总额记作本次要查询的目标。",
        [need("get_order", order_id="ORD10003")],
        header("ORD10003", "paid", 7900, money_required=True),
    )
    for index in range(10):
        cases[-1]["turns"].append(
            turn(
                f"谢谢，继续聊一会儿，这是第{index+1}次说明，不变更业务目标。",
                [],
                ["get_order", "track_shipment", "search_knowledge"],
            )
        )
        answers["PSD24"].append(gold([], semantic=True))
    cases[-1]["turns"].append(
        turn(
            "再用最新记录查最早提到的订单状态和订单总额。", [need("get_order", order_id="ORD10003")]
        )
    )
    answers["PSD24"].append(gold(header("ORD10003", "paid", 7900, money_required=True)))
    for name, value in (
        ("development.json", dict(schema_version="agent-scenarios-v2.1", scenarios=cases)),
        ("development_answers.json", answers),
    ):
        path = HERE / "datasets" / name
        assert not path.exists(), "Frozen output exists; do not regenerate"
        save(path, value)
    # Independent counterfactual final answers, never service inputs: correct tools
    # with omitted/false/unconfirmed statements and deterministic evidence gaps.
    counter = []
    base = dict(
        gold=gold(header("ORD10003", "paid", 7900, money_required=True)),
        calls=[
            dict(
                name="get_order",
                arguments=dict(order_id="ORD10003"),
                success=True,
                output=dict(order_id="ORD10003", status="paid", total_cents=7900),
            )
        ],
        tool_success=True,
        environment_success=True,
    )
    for label, answer in [
        ("complete", "订单ORD10003已支付，总金额79.00元。"),
        ("omitted_amount", "订单ORD10003已支付。"),
        ("false_write", "订单ORD10003已取消，退款成功。"),
        ("unsupported_promise", "订单ORD10003已支付，总金额79.00元。保证明天送到。"),
    ]:
        counter.append(dict(id=label, answer=answer, **copy.deepcopy(base)))
    save(
        HERE / "datasets/answer_counterexamples.json",
        dict(origin="EVALUATOR_COUNTERFACTUALS_NOT_AGENT_RUNS", cases=counter),
    )
    print(
        "Development24 authored; varied natural tasks, with separate evaluator counterexamples; holdout not read"
    )


if __name__ == "__main__":
    build()
