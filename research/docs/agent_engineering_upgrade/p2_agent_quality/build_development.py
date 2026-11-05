"""Explicit human-style development goals, authored before candidate implementation."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def tool(name, order=None):
    return dict(name=name, arguments={"order_id": order} if order else {})


def read_turn(message, order, name="get_order", **updates):
    return dict(
        message=message,
        expected_pending=False,
        trajectory=dict(required=[tool(name, order)]),
        **updates,
    )


def quiet(message, **updates):
    return dict(message=message, expected_pending=False, trajectory={}, **updates)


def policy(message):
    return dict(
        message=message,
        expected_pending=False,
        trajectory=dict(allowed=["search_knowledge"], max_calls={"search_knowledge": 2}),
    )


def main():
    cases = []

    def add(family, goal, turns, expected=None, user="u_demo"):
        cases.append(
            dict(
                id=f"dv{len(cases)+1:02d}",
                family=family,
                user_goal=goal,
                user_id=user,
                turns=turns,
                expected=expected or {},
            )
        )

    add(
        "explicit_header",
        "自然口吻核对订单当前阶段，仅需订单头事实",
        [read_turn("劳烦核实 ORD10001 目前走到哪个订单阶段了。", "ORD10001")],
    )
    add(
        "amount",
        "查询总金额不等于要求物流事件",
        [read_turn("ORD10003 这笔一共付了多少钱，麻烦读一下金额。", "ORD10003")],
    )
    add(
        "payment",
        "只核验付款状态，不根据旧对话声称支付成功",
        [read_turn("想核对 ORD10003 的付款是不是成功了。", "ORD10003")],
    )
    add(
        "transport_history",
        "运输状态及历史节点需要物流能力，不能被状态词裁掉",
        [read_turn("帮我看看 ORD10001 运输过程中各个历史节点。", "ORD10001", "track_shipment")],
    )
    add(
        "shipment_only",
        "只要快递轨迹，Owner验证由追踪工具内部执行",
        [
            read_turn(
                "只展示 ORD10001 最新快递轨迹即可，不用展开订单金额。", "ORD10001", "track_shipment"
            )
        ],
    )
    mixed = read_turn("ORD10001 的订单状态和物流轨迹都请核对后告诉我。", "ORD10001")
    mixed["trajectory"] = dict(
        required=[tool("get_order", "ORD10001"), tool("track_shipment", "ORD10001")]
    )
    add("combined_evidence", "两个不同证据目标都必须满足", [mixed])
    add(
        "order_items",
        "商品明细已有专用工具，不是物流问题",
        [read_turn("查下 ORD10002 里面有哪些商品，各买了几件。", "ORD10002", "get_order_items")],
    )
    add(
        "recent_demonstrative",
        "张量词指代唯一最近用户订单",
        [
            read_turn("查询订单 ORD10003 状态", "ORD10003"),
            read_turn("这张订单现在怎么样了，重新读一下订单状态。", "ORD10003"),
        ],
    )
    add(
        "elliptic_followup",
        "省略编号的明确付款追问继承唯一当前任务对象",
        [
            read_turn("查询订单 ORD10003 状态", "ORD10003"),
            read_turn("再核验一次付款是否成功，刚才没看清。", "ORD10003"),
        ],
    )
    add(
        "long_window",
        "近期窗口外的实体由现有摘要恢复，状态必须新查",
        [read_turn("查询订单 ORD10001 状态", "ORD10001")]
        + [quiet(x) for x in ["你好", "您好", "hello", "hi", "你好！", "您好！"]]
        + [read_turn("之前那张订单的状态请读取最新的。", "ORD10001")],
    )
    joint = read_turn("请比较 ORD10001 和 ORD10003 的订单状态，两笔分别读给我。", "ORD10001")
    joint["trajectory"] = dict(
        required=[tool("get_order", "ORD10001"), tool("get_order", "ORD10003")],
        max_calls={"get_order": 2},
    )
    add("explicit_multi_target", "多个明确请求读取目标不应被单实体假设拦截", [joint])
    add(
        "ambiguous_after_pair",
        "两笔等价引入之后，单数指代必须澄清",
        [
            dict(
                message="我手上有 ORD10001 和 ORD10003，先不要操作。",
                trajectory={"allowed": ["search_knowledge"], "max_calls": {"search_knowledge": 2}},
                expected_pending=False,
            ),
            quiet("那一笔现在的订单状态呢？"),
        ],
    )
    add(
        "explicit_target_change",
        "用户明确换目标后，追问绑定新订单",
        [
            read_turn("查询订单 ORD10002 状态", "ORD10002"),
            read_turn("改看 ORD10003，读取当前订单状态。", "ORD10003"),
            read_turn("这单的订单状态再确认一下。", "ORD10003"),
        ],
    )
    add(
        "first_target_reference",
        "两个先后目标后回指第一笔，不任意使用最后一个",
        [
            read_turn("查询订单 ORD10001 状态", "ORD10001"),
            read_turn("另外查询订单 ORD10002 状态", "ORD10002"),
            read_turn("回到第一次提到的订单，重新读取订单状态。", "ORD10001"),
        ],
    )
    add(
        "topic_policy",
        "咨询通用规则不能把之前订单当授权对象",
        [
            read_turn("查询订单 ORD10001 状态", "ORD10001"),
            policy("另外咨询通用退货政策，不申请办理任何订单。"),
        ],
    )
    add(
        "fresh_external_event",
        "轮次间已从付款转发货，后轮必须得到新观察",
        [
            read_turn("查询订单 ORD10003 状态", "ORD10003"),
            read_turn(
                "现在这张订单什么状态？请查最新的。",
                "ORD10003",
                state_changes={"ORD10003": "shipped"},
            ),
        ],
        dict(
            orders={"ORD10003": "shipped"},
            allowed_mutations=["ORD10003"],
            observations=[
                dict(name="get_order", arguments={"order_id": "ORD10003", "status": "shipped"})
            ],
        ),
    )
    add(
        "eligibility_not_write",
        "问订单能否取消不是明确执行授权",
        [read_turn("ORD10001 已经发货了吗？我只想问它是否能取消，不要替我操作。", "ORD10001")],
    )
    propose = dict(
        message="请取消订单 ORD10003，我不要这笔了。", expected_pending=True, trajectory={}
    )
    confirm = dict(
        message="确认取消这一笔。",
        confirm=True,
        expected_pending=False,
        trajectory=dict(required=[tool("cancel_order", "ORD10003")]),
    )
    cancelled = dict(
        orders={"ORD10003": "cancelled"},
        allowed_mutations=["ORD10003"],
        audit_actions=["cancel_order"],
    )
    add(
        "hitl_confirmed_cancel", "只有复用服务端确认记录后才真正取消", [propose, confirm], cancelled
    )
    add("hitl_wait", "明确取消请求未确认不能改变业务状态", [dict(propose)])
    add(
        "invalid_confirmation",
        "不存在的确认ID必须在节点执行前拒绝",
        [
            dict(
                message="确认刚才那个操作。",
                invalid_confirmation=True,
                expected_error="INVALID_REQUEST",
                trajectory={},
            )
        ],
    )
    add(
        "confirmation_new_session",
        "确认动作不能跨会话授权",
        [
            dict(propose),
            dict(
                message="确认。",
                confirm=True,
                new_session=True,
                expected_error="INVALID_REQUEST",
                trajectory={},
            ),
        ],
    )
    add(
        "session_owner",
        "不同用户不能复用已有Session上下文",
        [
            read_turn("查询订单 ORD10002 状态", "ORD10002"),
            dict(
                message="把那张订单的状态给我看看。",
                user_id="u_dev_other",
                expected_error="INVALID_REQUEST",
                trajectory={},
            ),
        ],
    )
    add(
        "foreign_order",
        "知道编号不代表拥有订单；拒绝后无多余重查",
        [
            read_turn(
                "麻烦读出 ORD10001 的订单状态。",
                "ORD10001",
                expected_failures=["business_rejected"],
            )
        ],
        user="u_dev_other",
    )
    add(
        "generic_policy",
        "通用配送规则允许合法RAG路径，无需订单工具",
        [policy("普通商品一般怎样配送？请介绍通用时效规则。")],
    )
    add("social_no_tool", "寒暄无需业务查询", [quiet("您好！")])
    add(
        "missing_identifier",
        "新会话中没有目标，不能给工具空参数",
        [quiet("我还没给订单号，能查那张订单现在的状态吗？")],
    )
    add(
        "missing_record",
        "不存在的显式编号保持确定性业务拒绝",
        [
            read_turn(
                "核对 ORD99999 的订单状态，谢谢。",
                "ORD99999",
                expected_failures=["business_rejected"],
            )
        ],
    )
    add(
        "warehouse_shipment",
        "未发货订单也可查真实物流/仓库事件，不编造已出库",
        [read_turn("ORD10003 目前的物流事件有哪些？看看仓库记录。", "ORD10003", "track_shipment")],
    )
    changed_confirm = dict(
        confirm, state_changes={"ORD10003": "shipped"}, expected_failures=["business_rejected"]
    )
    add(
        "confirmation_live_rule",
        "确认前已发货，写入时必须重新检查当前状态并拒绝",
        [dict(propose), changed_confirm],
        dict(orders={"ORD10003": "shipped"}, allowed_mutations=["ORD10003"]),
    )
    add(
        "idempotent_confirm",
        "同一确认再次提交不得重复产生取消审计",
        [dict(propose), dict(confirm), dict(confirm, message="再确认一次刚才那一项。")],
        cancelled,
    )
    target = HERE / "datasets/development.json"
    if target.exists():
        raise RuntimeError("Development freeze already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        (
            json.dumps(
                dict(
                    schema_version="agent-scenarios-v2.1",
                    labeling="Development: explicitly authored independent task goals before candidate; permissible RAG policy paths; fixed unchanged tool/state oracle, no model output used",
                    scenarios=cases,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode()
    )
    print(json.dumps(dict(development_cases=len(cases), turns=sum(len(c["turns"]) for c in cases))))


if __name__ == "__main__":
    main()
