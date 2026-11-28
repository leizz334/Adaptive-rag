from app.agents.goals import resolve_goals
from app.schemas.goals import GoalKind, GoalSignal


def hints(*signals):
    return [GoalSignal.model_validate(signal) for signal in signals]


def test_background_is_grounded_and_does_not_add_an_action():
    query = "替同事整理账本。ORD10001 的实付金额麻烦查一下。"
    goals = resolve_goals(
        query,
        suggestions=hints({"category": "background", "quote": "替同事整理账本"}),
    )
    assert [(goal.kind, goal.entity_id) for goal in goals] == [(GoalKind.ORDER_AMOUNT, "ORD10001")]
    unsupported_hint = hints({"category": "background", "quote": "替同事"})
    assert any(
        goal.kind == GoalKind.UNKNOWN for goal in resolve_goals(query, suggestions=unsupported_hint)
    )


def test_fields_join_their_goal_and_unavailable_fields_do_not_claim_evidence():
    query = "查 ORD10001 物流轨迹。要有最近一个扫描地点。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {"category": "action", "kind": "shipment", "quote": "物流轨迹"},
            {
                "category": "field",
                "kind": "shipment",
                "quote": "要有最近一个扫描地点",
                "fields": ["scan_location"],
            },
        ),
    )
    (shipment,) = goals
    assert shipment.fields == ("events",)
    assert shipment.unavailable_fields == ("scan_location",)


def test_explicit_missing_field_only_does_not_request_substitute_tracking_facts():
    query = "ORD10001 的快递预计哪日送达？"
    (shipment,) = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "action",
                "kind": "shipment",
                "quote": "快递预计哪日送达",
                "fields": ["estimated_delivery_at"],
            },
        ),
    )
    assert shipment.fields == ()
    assert shipment.unavailable_fields == ("estimated_delivery_at",)


def test_field_cannot_join_a_different_order_and_unresolved_independence_needs_full_clause():
    query = "查 ORD10001 商品明细。ORD10002 要列定制款。还想核对积分余额。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "field",
                "kind": "order_items",
                "quote": "ORD10002 要列定制款",
                "fields": ["items.customized"],
            },
            {
                "category": "unresolved",
                "quote": "积分余额",
                "operation": "read",
                "independent": True,
            },
        ),
    )
    assert [goal.entity_id for goal in goals if goal.kind == GoalKind.ORDER_ITEMS] == ["ORD10001"]
    assert all(not goal.independent for goal in goals)
    goals = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "unresolved",
                "quote": "还想核对积分余额",
                "operation": "read",
                "independent": True,
            }
        ),
    )
    unresolved = next(goal for goal in goals if goal.independent)
    assert unresolved.operation == "read"
    assert unresolved.request_text == "还想核对积分余额"


def test_coverage_checks_cannot_hide_negation_write_and_dependency():
    query = "查 ORD10001 订单状态。如果还没出库，帮我取消 ORD10001。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {"category": "background", "quote": "帮我取消 ORD10001"},
            {"category": "constraint", "quote": "查 ORD10001 订单状态"},
        ),
    )
    cancel = next(goal for goal in goals if goal.kind == GoalKind.CANCEL)
    assert cancel.operation == "write" and cancel.conditions
    assert any(goal.kind == GoalKind.ORDER_STATUS for goal in goals)


def test_dependency_can_cover_language_beyond_legacy_conditional_pattern():
    query = "查 ORD10001 的实付金额。金额超过两百才查 ORD10001 物流轨迹。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {"category": "dependency", "quote": "金额超过两百才查 ORD10001 物流轨迹"}
        ),
    )
    assert any(goal.conditions for goal in goals if goal.kind == GoalKind.SHIPMENT)


def test_explicit_exclusion_can_narrow_a_grounded_semantic_read():
    query = "查 ORD10001 订单状态。物流先放一边。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "constraint",
                "kind": "shipment",
                "quote": "物流先放一边",
                "negated": True,
            },
        ),
    )
    assert [goal.kind for goal in goals if not goal.negated] == [GoalKind.ORDER_STATUS]


def test_a_coordinated_field_span_can_describe_one_read():
    query = "查 ORD10001 物流轨迹和最新扫描地点。"
    (goal,) = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "action",
                "kind": "shipment",
                "quote": "物流轨迹和最新扫描地点",
                "fields": ["events", "scan_location"],
            },
        ),
    )
    assert goal.fields == ("events",) and goal.unavailable_fields == ("scan_location",)


def test_soft_clause_boundary_cannot_enable_independent_unresolved_read():
    query = "查 ORD10001 实付金额，结果也用来核对积分余额。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "unresolved",
                "quote": "结果也用来核对积分余额",
                "operation": "read",
                "independent": True,
            },
        ),
    )
    assert not any(goal.independent for goal in goals)


def test_role_labels_cannot_drop_raw_write_or_unambiguous_read():
    query = "查 ORD10001 的状态。请查物流。取消 ORD10001。"
    goals = resolve_goals(
        query,
        suggestions=hints(
            {"category": "background", "quote": "请查物流"},
            {"category": "constraint", "kind": "cancel", "quote": "取消 ORD10001", "negated": True},
        ),
    )
    assert {goal.kind for goal in goals if not goal.negated} == {
        GoalKind.ORDER_STATUS,
        GoalKind.SHIPMENT,
        GoalKind.CANCEL,
    }


def test_removing_background_does_not_resolve_an_ambiguous_sku():
    query = "SKU-FIRST 是上次看到的。查这款的库存。SKU-SECOND 也查库存。"
    goals = resolve_goals(
        query,
        suggestions=hints({"category": "background", "quote": "SKU-FIRST 是上次看到的"}),
    )
    assert [goal.entity_id for goal in goals if goal.kind == GoalKind.INVENTORY] == [
        None,
        "SKU-SECOND",
    ]


def test_product_attributes_can_be_present_in_description_and_named_projection_stays_exact():
    query = "SKU-SCARF 是什么纤维？"
    (goal,) = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "action",
                "quote": "是什么纤维",
                "kind": "product_detail",
                "fields": ["product_attribute"],
            },
        ),
    )
    assert goal.fields == ("name", "description") and goal.unavailable_fields == (
        "product_attribute",
    )
    (goal,) = resolve_goals(
        query,
        suggestions=hints(
            {
                "category": "action",
                "quote": "是什么纤维",
                "kind": "product_detail",
                "fields": ["name"],
            },
        ),
    )
    assert goal.fields == ("name",)


def test_declared_identifier_supplies_entity_without_an_extra_goal():
    (goal,) = resolve_goals("我指的是 ORD10003，核对订单状态。")
    assert goal.kind == GoalKind.ORDER_STATUS and goal.entity_id == "ORD10003"
