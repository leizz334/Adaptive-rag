"""Ground task hints in the current request and reuse P1's entity provenance.

The bounded offline fallback adapts the earlier read-goal mapping from 37a7e47.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.agents.dependencies import bind_payment_dependency
from app.core.enums import IntentLabel
from app.memory.context import ORDER_PATTERN, SelectedContext, user_orders
from app.schemas.goals import (
    GOAL_FIELDS,
    DependencyHint,
    EntityScope,
    EntitySource,
    EntityType,
    GoalKind,
    GoalSignal,
    TaskGoal,
    goal_read_fields,
)

G = GoalKind
SKU_RE = re.compile(r"(?<![A-Za-z0-9_-])SKU[-_][A-Za-z0-9_-]+", re.I)
_CLAUSE = re.compile(
    r"[，,。；;！!？?\n]|以及|并且|同时|顺便|另外|接着|然后|但是|不过|而是"
    r"|再查(?=\s*(?:ORD|SKU))|(?=(?:只|仅)(?:查|看|查询|查看|想查|想看))"
    r"|(?=(?:不用|不必|不要|不|无需|(?<!分)别)查)"
)
_QUOTED = re.compile(r"「[^」]*」|『[^』]*』|“[^”]*”|\"[^\"]*\"")
_NEGATIVE = re.compile(
    r"不要|不用|不必|不需要|不查|不看|无需|(?<!分)别(?=查|看|取消|退)|不想(?:查|看|取消|退)"
)
_COORDINATION = re.compile(r"、|和|与")
_SENTENCE = re.compile(r"[。；;！!？?\n]")
_DISTRIBUTIVE = re.compile(r"分别|逐(?:一|笔|款)|各(?=自|的|有|剩|还|需|为|是|查|看|多少|\s)")
_DISTRIBUTIVE_REFERENCE = re.compile(r"这([两二三四五六]|\d+)(?:笔|单|款|个)(?:订单|商品)?")
_REFERENCE_NUMBERS = str.maketrans("两二三四五六", "223456")
_ENTITY_JOIN = re.compile(r"\s*(?:、|和|与|及|以及)\s*")
_ILLUSTRATION = re.compile(r"例如|比如|举例|示例")
_ORDER_TOPIC = re.compile(r"订单|[这那]单|[这那]笔")
_CONDITIONAL = re.compile(r"如果|假如|假设|要是|只要|倘若|万一")
_LIMITATION = re.compile(r"(?:只|仅)(?:查|看|查询|查看|想查|想看|需要)|不要|无须|(?<!分)别查")
_PRESENTATION = re.compile(
    r"^(?:(?:之后的)?(?:客服)?回复)?请(?:简短|简洁|简单)(?:一?点|回答)?$"
    r"|^(?:只|仅)(?:要|需)[^，。！？；]{1,30}(?:就行|即可|就好|就够了)$"
)
_ORDER_ID_WAIT = re.compile(
    r"(?:先)?(?:等|等到)我(?:(?:把)?(?:订单号|单号)(?:找(?:到|出来)|补(?:上|齐)|发来)"
    r"|(?:找到|补上|提供|发来)(?:订单号|单号))(?:再查)?"
)
_NON_TASK = re.compile(r"^(?:谢谢(?:你|您)?|辛苦了|麻烦了|请问|你好|您好|我用手机看)$")
_REPORT_RESULT = re.compile(r"(?:告诉我|说明|说一声|注明)$")
_READ_VERBS = r"查|核对|确认|看一下|告诉我"
_READ_REQUEST = re.compile(rf"帮我|请|{_READ_VERBS}")
_READ_ACTION = re.compile(_READ_VERBS)
_REQUEST_START = re.compile(rf"^(?:帮我|请|麻烦)?\s*(?:{_READ_VERBS})")
_TASK_LINK = re.compile(
    r"后才|后再|再决定|取决于|为前提|(?<!刚)才(?:能|给我|帮我)?(?=查|看|核对|确认|取消|申请)"
    r"|(?:(?:支付|付款|扣款)(?:成功|失败)|(?:已|未|没)(?:支付|付款|发货|签收))"
    r"\s*再(?=查|看|核对|确认|取消|申请)"
    r"|(?:确认|确定|核实)[^，。；]{1,48}(?:再|才)(?:帮我|给我|能)?(?=查|看|列|核对|取消|申请)"
)
_IDENTIFIER_DECLARATION = re.compile(r"^(?:我(?:说|指)的|订单号|单号|SKU)(?:是|为|[：:])\s*", re.I)
_POLICY = re.compile(r"规则|规定|政策|条件|流程|手续费|怎么算|一般|通常|怎么退")
_ELIGIBILITY = re.compile(r"能不能|能否|可不可以|可以吗|是否可以")
_WRITE_PATTERNS = {
    G.CANCEL: re.compile(r"(?:取消|撤销)\s*(?:订单|ORD|这单|那单)|请(?:帮我)?撤掉|不想要了"),
    G.REFUND_REQUEST: re.compile(r"申请退款|提交退款|(?:帮我|我要)退款"),
    G.RETURN_REQUEST: re.compile(
        r"申请退货|提交退货|(?:帮我|我要)退货|(?:提交|发起|办理|开(?:个|一份)?)\s*退货申请"
    ),
}
_READ_PATTERNS = {
    G.ORDER_STATUS: re.compile(r"状态|订单阶段|处理阶段|进度|发货|出库|订单处理到哪"),
    G.ORDER_PAYMENT: re.compile(r"支付状态|付款状态|(?:支付|付款|扣款)(?:成功|了|了吗|没有|没)"),
    G.ORDER_AMOUNT: re.compile(r"金额|实付|总额|总价|合计|一共花|(?:付了)?多少钱|付了多少"),
    G.ORDER_ITEMS: re.compile(r"明细|买了什么|哪些商品|买的东西|各买|几件|几样|数量|是否定制"),
    G.SHIPMENT: re.compile(
        r"物流|快递|轨迹|运输|配送|包裹|节点|到哪|什么时候能到|哪天送到|几号能送到"
    ),
    G.TRACKING_NUMBER: re.compile(r"(?:运单|快递单|物流单)号"),
    G.REFUND_STATUS: re.compile(
        r"退款(?:处理|审核)?(?:单|记录|进度|进展|状态|到哪|到没|到账|什么时候)|退了多少|(?:退款|退的款).*到账"
    ),
    G.INVENTORY: re.compile(r"库存|现货|有货|剩(?:下)?(?:多少|几件)"),
    G.PRODUCT_DETAIL: re.compile(r"详情|详细资料|规格|参数|介绍|材质"),
    G.PRODUCT_PRICE: re.compile(r"价格|售价|单价|多少钱"),
}
_PRODUCT = {G.INVENTORY, G.PRODUCT_DETAIL, G.PRODUCT_PRICE}
_ORDER = set(_READ_PATTERNS) - _PRODUCT
_UNAVAILABLE_FIELDS = {
    G.SHIPMENT: {"scan_location", "estimated_delivery_at"},
    G.PRODUCT_DETAIL: {"product_attribute"},
}
_UNAVAILABLE_FIELD_TEXT = {
    "scan_location": re.compile(r"扫描|地点|位置"),
    "estimated_delivery_at": re.compile(r"预计|送到|到货|送达"),
    "product_attribute": re.compile(r"材料|材质|尺寸|型号|规格|成分|属性"),
}
GOAL_INTENTS = {
    **dict.fromkeys(
        {G.ORDER_STATUS, G.ORDER_PAYMENT, G.ORDER_AMOUNT, G.ORDER_ITEMS}, IntentLabel.ORDER_INQUIRY
    ),
    **dict.fromkeys({G.SHIPMENT, G.TRACKING_NUMBER}, IntentLabel.LOGISTICS),
    **dict.fromkeys(_PRODUCT, IntentLabel.PRODUCT_CONSULT),
    G.REFUND_STATUS: IntentLabel.REFUND,
    G.POLICY: IntentLabel.FAQ_POLICY,
}


def _clause_goals(text: str, *, order: bool, product: bool) -> list[GoalKind]:
    if _POLICY.search(text) and not _NEGATIVE.search(text) and not _CONDITIONAL.search(text):
        return [G.POLICY]
    writes = [kind for kind, pattern in _WRITE_PATTERNS.items() if pattern.search(text)]
    if writes and _ELIGIBILITY.search(text):
        return [G.ORDER_STATUS] if order and writes == [G.CANCEL] else [G.POLICY]
    refund = _READ_PATTERNS[G.REFUND_STATUS].search(text)
    # Domain qualifiers decide what a generic state or progress phrase describes.
    header = re.sub(r"(?:物流|快递|运输|配送)(?:的)?(?:状态|进度)", "", text)
    header = re.sub(r"(?:支付|付款)(?:的)?状态", "", header)
    matches = []
    for kind, pattern in _READ_PATTERNS.items():
        sample = header if kind == G.ORDER_STATUS else text
        match = pattern.search(sample)
        if not match:
            continue
        if kind == G.ORDER_ITEMS and not order and _READ_PATTERNS[G.INVENTORY].search(text):
            continue
        if kind in {G.ORDER_STATUS, G.SHIPMENT} and refund:
            if kind == G.ORDER_STATUS or not re.search(r"物流|快递|包裹|运输", text):
                continue
        if (
            kind == G.ORDER_AMOUNT
            and refund
            and not re.search(r"实付|订单金额|支付金额|下单金额", text)
        ):
            continue
        if (
            kind == G.SHIPMENT
            and _READ_PATTERNS[G.TRACKING_NUMBER].search(text)
            and not re.search(r"轨迹|状态|进度|到哪|运输|节点", text)
        ):
            continue
        if kind == G.ORDER_STATUS and writes and not re.search(r"查|看|核实|确认", text):
            continue
        if (
            product
            and not order
            and kind in _ORDER
            and kind not in {G.SHIPMENT, G.TRACKING_NUMBER, G.REFUND_STATUS}
        ):
            continue
        if kind == G.PRODUCT_PRICE and "多少钱" in text and not product:
            continue
        matches.append((match.start(), kind))
    return writes + [kind for _, kind in sorted(matches, key=lambda item: item[0])]


def _clauses(text: str, coherent: Sequence[str] = ()) -> list[str]:
    clauses = [
        part.strip()
        for group in _CLAUSE.split(text)
        for part in (
            [group]
            if _NEGATIVE.search(group)
            or _DISTRIBUTIVE.search(group)
            or any(quote in group for quote in coherent)
            else _COORDINATION.split(group)
        )
        if part.strip()
    ]
    joined: list[str] = []
    for clause in clauses:
        if (
            joined
            and _LIMITATION.match(clause)
            and (ORDER_PATTERN.fullmatch(joined[-1]) or SKU_RE.fullmatch(joined[-1]))
            and re.search(re.escape(joined[-1]) + r"\s+" + re.escape(clause), text)
        ):
            joined[-1] += " " + clause
        else:
            joined.append(clause)
    return joined


def _skus(text: str) -> list[str]:
    return list(dict.fromkeys(sku.upper() for sku in SKU_RE.findall(text)))


def _explicit_entity_list(text: str, pattern: re.Pattern[str], identifiers: list[str]) -> bool:
    matches = list(pattern.finditer(text))
    return (
        len(matches) == len(identifiers) >= 2
        and [match[0].upper() for match in matches] == identifiers
        and all(
            _ENTITY_JOIN.fullmatch(text[left.end() : right.start()])
            for left, right in zip(matches, matches[1:], strict=False)
        )
    )


def _distributes(
    clause: str, entity_text: str, pattern: re.Pattern[str], local: list[str], candidates: list[str]
) -> bool:
    if not _DISTRIBUTIVE.search(clause) or _NEGATIVE.search(clause):
        return False
    if local:
        return _explicit_entity_list(clause, pattern, local)
    reference = _DISTRIBUTIVE_REFERENCE.search(clause)
    if reference is None or reference[1].translate(_REFERENCE_NUMBERS) != str(len(candidates)):
        return False
    return any(
        _explicit_entity_list(sentence, pattern, candidates)
        for sentence in _SENTENCE.split(entity_text)
    )


def _resolve_lexical_goals(
    text: str,
    context: SelectedContext | None,
    suggestions: Sequence[GoalSignal],
    coherent: Sequence[str] = (),
    entity_text: str | None = None,
    unresolved_reads: dict[str, GoalSignal] | None = None,
) -> list[TaskGoal]:
    entity_text = text if entity_text is None else entity_text
    unresolved_reads = unresolved_reads or {}
    clauses = [
        clause
        for sentence in _SENTENCE.split(text)
        for clause in (
            [sentence.strip()]
            if sentence.strip() in unresolved_reads
            else _clauses(sentence, coherent)
        )
    ]
    all_orders = user_orders(entity_text)
    all_skus = _skus(entity_text)
    identifiers = {*all_orders, *all_skus}
    reporting = {
        clause
        for clause in clauses
        if _CONDITIONAL.match(clause)
        and _REPORT_RESULT.search(clause)
        and not any(pattern.search(clause) for pattern in _WRITE_PATTERNS.values())
    }
    constraints = tuple(
        clause
        for clause in clauses
        if _LIMITATION.search(clause) or _PRESENTATION.fullmatch(clause) or clause in reporting
    )
    goals: dict[tuple, TaskGoal] = {}
    pending_condition = None
    for clause in clauses:
        if (
            _IDENTIFIER_DECLARATION.sub("", clause).upper() in identifiers
            or _NON_TASK.fullmatch(clause)
            or _PRESENTATION.fullmatch(clause)
            or clause in reporting
        ):
            continue
        negated = bool(_NEGATIVE.search(clause))
        local_orders = user_orders(clause)
        local_skus = _skus(clause)
        orders = local_orders or ([] if local_skus else all_orders)
        skus = local_skus or ([] if local_orders else all_skus)
        remembered_sku = context.product_sku if context and not orders and not skus else None
        order_subject = bool(local_orders or (not local_skus and _ORDER_TOPIC.search(clause)))
        catalog = (
            not orders
            and not order_subject
            and not (context and context.order_id)
            and any(signal.kind in _PRODUCT and signal.quote in clause for signal in suggestions)
        )
        product = bool(skus or remembered_sku or (context and context.product_name)) or catalog
        kinds = _clause_goals(clause, order=bool(orders) or order_subject, product=product)
        if _CONDITIONAL.match(clause):
            pending_condition = clause
            if not any(kind in _WRITE_PATTERNS for kind in kinds) and not _READ_REQUEST.search(
                clause
            ):
                continue
        conditions = (pending_condition,) if pending_condition else ()
        pending_condition = None
        for signal in suggestions:
            if (
                not any(kind in _WRITE_PATTERNS for kind in kinds)
                and signal.kind not in kinds
                and signal.kind in _READ_PATTERNS
                and signal.quote in clause
                and signal.quote.upper() not in {*orders, *skus}
                and (
                    (signal.kind in _ORDER and (orders or context and context.order_id))
                    or (signal.kind in _PRODUCT and product)
                )
            ):
                lexical = _clause_goals(signal.quote, order=bool(orders), product=product)
                if not lexical or signal.kind in lexical:
                    kinds.append(signal.kind)
        unresolved = unresolved_reads.get(clause)
        if not kinds and unresolved and unresolved.kind in _READ_PATTERNS:
            kinds.append(unresolved.kind)
        if not kinds and re.fullmatch(
            r"(?:之前|刚才)?(?:我)?已经申请了|(?:订单号|单号)(?:是)?\s*ORD\d+", clause, re.I
        ):
            continue
        for kind in kinds or [G.UNKNOWN]:
            write = kind in _WRITE_PATTERNS
            entity_type: EntityType = "none"
            entity_id = None
            source: EntitySource = "none"
            clarification: tuple[str, ...] = ()
            if kind in _ORDER or write:
                entity_type = "order"
                entity_id = orders[0] if len(orders) == 1 else None
                source = "current_user" if entity_id else "none"
                if (
                    not orders
                    and context
                    and context.order_id
                    and (
                        (origin := context.source) == "session_user"
                        or origin == "session_summary_user_entity"
                    )
                ):
                    entity_id = context.order_id
                    source = (
                        "session_user"
                        if origin == "session_user"
                        else "session_summary_user_entity"
                    )
                clarification = () if entity_id else ("order_id",)
            elif kind in _PRODUCT:
                entity_type = "product"
                entity_id = skus[0] if len(skus) == 1 else None
                source = "current_user" if entity_id else "none"
                if (
                    remembered_sku
                    and context
                    and context.product_source
                    in {
                        "session_user",
                        "session_summary_user_entity",
                    }
                ):
                    entity_id = remembered_sku
                    source = context.product_source
                clarification = () if entity_id else ("sku",)
            elif kind == G.UNKNOWN:
                clarification = ("request",)
            local = local_orders if entity_type == "order" else local_skus
            candidates = orders if entity_type == "order" else skus
            distributed = (
                not write
                and not conditions
                and entity_type != "none"
                and not (local_orders and local_skus)
                and _distributes(
                    clause,
                    entity_text,
                    ORDER_PATTERN if entity_type == "order" else SKU_RE,
                    local,
                    candidates,
                )
            )
            entity_scope: EntityScope = "none"
            if entity_id:
                entity_scope = (
                    "context" if source != "current_user" else "local" if local else "request"
                )
            independent = bool(
                unresolved
                and not negated
                and not conditions
                and not write
                and (kind == G.UNKNOWN or (not candidates and unresolved.kind == kind))
                and entity_id is None
            )
            for target in candidates if distributed else (entity_id,):
                goal = TaskGoal(
                    kind=kind,
                    request_text=clause,
                    fields=GOAL_FIELDS.get(kind, ()),
                    negated=negated,
                    constraints=constraints,
                    conditions=conditions,
                    operation="write"
                    if write
                    else "unknown"
                    if kind == G.UNKNOWN and not independent
                    else "read",
                    entity_type=entity_type,
                    entity_id=target,
                    entity_source="current_user" if distributed else source,
                    entity_scope="distributive" if distributed else entity_scope,
                    clarification=() if distributed else clarification,
                    independent=independent,
                )
                key = (kind, target, negated, clause if not target or conditions else "")
                previous = goals.get(key)
                if not previous or (entity_scope == "local" and previous.entity_scope == "request"):
                    goals[key] = goal
    if pending_condition:
        goals[(G.UNKNOWN, pending_condition)] = TaskGoal(
            kind=G.UNKNOWN,
            request_text=pending_condition,
            operation="unknown",
            conditions=(pending_condition,),
            clarification=("dependent_goal",),
        )
    return list(goals.values())


def _apply_field_signals(goals: list[TaskGoal], signals: Sequence[GoalSignal]) -> set[str]:
    attached: set[str] = set()
    for signal in signals:
        if signal.category not in {"action", "field"} or not signal.fields:
            continue
        orders = user_orders(signal.quote)
        skus = _skus(signal.quote)
        matches = [
            index
            for index, goal in enumerate(goals)
            if goal.kind == signal.kind
            and goal.operation == "read"
            and not goal.negated
            and (not (orders or skus) or goal.entity_id in {*orders, *skus})
        ]
        local = [index for index in matches if signal.quote in goals[index].request_text]
        candidates = local or (matches if signal.category == "field" else [])
        default_fields = GOAL_FIELDS.get(signal.kind, ())
        requested = set(signal.fields)
        available = goal_read_fields(signal.kind)
        supported = tuple(field for field in available if field in requested)
        unavailable = requested.intersection(_UNAVAILABLE_FIELDS.get(signal.kind, ()))
        if not (supported or unavailable):
            continue
        if not candidates:
            if _record_unavailable_field(goals, signal, unavailable, supported, [*orders, *skus]):
                attached.add(signal.quote)
            continue
        if len(candidates) > 1 and not (
            candidates == local
            and all(goals[index].entity_scope == "distributive" for index in local)
            and len({goals[index].request_text for index in local}) == 1
        ):
            continue
        for index in candidates:
            goal = goals[index]
            # The directory may include the attribute as free text, even without a separate field.
            from_description = goal.kind == G.PRODUCT_DETAIL and "product_attribute" in unavailable
            fields = default_fields if from_description else supported
            if signal.category == "field":
                fields = tuple(dict.fromkeys((*goal.fields, *fields)))
            goals[index] = goal.model_copy(
                update={
                    "fields": fields,
                    "unavailable_fields": tuple(
                        dict.fromkeys((*goal.unavailable_fields, *sorted(unavailable)))
                    ),
                }
            )
        if signal.category == "field":
            attached.add(signal.quote)
    return attached


def _record_unavailable_field(
    goals: list[TaskGoal],
    signal: GoalSignal,
    unavailable: set[str],
    supported: tuple[str, ...],
    mentioned_ids: list[str],
) -> bool:
    if (
        signal.category != "field"
        or supported
        or not unavailable
        or not all(_UNAVAILABLE_FIELD_TEXT[field].search(signal.quote) for field in unavailable)
        or not any(
            goal.kind == G.UNKNOWN
            and goal.request_text == signal.quote
            and not (goal.conditions or goal.negated)
            for goal in goals
        )
    ):
        return False
    domain = "product" if signal.kind in _PRODUCT else "order"
    candidates = {
        goal.entity_id: goal
        for goal in goals
        if goal.entity_type == domain
        and goal.entity_id
        and goal.operation == "read"
        and not (goal.conditions or goal.negated)
        and (not mentioned_ids or goal.entity_id in mentioned_ids)
    }
    if len(candidates) != 1:
        return False
    anchor = next(iter(candidates.values()))
    goals.append(
        anchor.model_copy(
            update={
                "kind": signal.kind,
                "request_text": signal.quote,
                "fields": (),
                "entity_scope": "local" if mentioned_ids else "request",
                "unavailable_fields": tuple(sorted(unavailable)),
            }
        )
    )
    return True


def _affirmative_request(quote: str, text: str) -> bool:
    followed_by_question = text.partition(quote)[2].lstrip().startswith(("?", "？"))
    return bool(_REQUEST_START.match(quote)) or followed_by_question


def _background_boundary(quote: str, text: str, clauses: list[str]) -> bool:
    if quote in clauses:
        return True
    for clause in re.split(r"[，,。；;！!？?\n]", text):
        prefix, match, suffix = clause.strip().partition(quote)
        if (
            match
            and not suffix
            and prefix.strip().upper() in {*user_orders(prefix), *_skus(prefix)}
        ):
            return True
    return False


def _preserve_explicit_reads(
    text: str, goals: list[TaskGoal], signals: Sequence[GoalSignal]
) -> list[TaskGoal]:
    """Keep an unclassified opening statement separate from self-contained later reads."""
    first = re.match(r"\s*([^。；;！？!?\n]+)[。；;\n]", text)
    if not first:
        return goals
    preface = first[1].strip()
    unknown = [
        g
        for g in goals
        if g.kind == G.UNKNOWN and g.request_text == preface and not (g.negated or g.conditions)
    ]
    if (
        len(unknown) != 1
        or _READ_REQUEST.search(preface)
        or _CONDITIONAL.search(preface)
        or any(signal.quote in preface for signal in signals)
    ):
        return goals
    reads = [g for g in goals if g is not unknown[0]]
    targets = {g.entity_id for g in reads if g.entity_id}
    if (
        len(targets) < 2
        or targets != set(user_orders(text))
        or not all(
            g.operation == "read"
            and not (g.conditions or g.clarification or g.negated)
            and g.entity_type == "order"
            and g.entity_scope == "local"
            and g.entity_source == "current_user"
            and g.request_text in text[first.end() :]
            for g in reads
        )
    ):
        return goals
    # Preserve the residual as unknown; only the two explicitly bound reads may run.
    return [g.model_copy(update={"independent": True}) if g is unknown[0] else g for g in goals]


def resolve_goals(
    query: str,
    context: SelectedContext | None = None,
    suggestions: Sequence[GoalSignal] = (),
    *,
    dependency_hints: Sequence[DependencyHint] = (),
) -> list[TaskGoal]:
    """Validate semantic spans against the request, with P2 as the no-hint fallback."""
    raw = _QUOTED.sub(lambda matched: " " * len(matched[0]), query.partition("（会话指代：")[0])
    if (
        context
        and context.resumed_goal
        and context.order_id
        and context.source
        in {
            "current_user",
            "session_user",
            "session_summary_user_entity",
        }
    ):
        prior = context.resumed_goal
        return [
            prior.model_copy(
                update={
                    "request_text": raw,
                    "entity_id": context.order_id,
                    "entity_source": context.source,
                    "clarification": (),
                    "entity_scope": "local" if context.source == "current_user" else "context",
                }
            )
        ]
    text = raw
    if context and context.source == "current_user" and context.order_id:
        text = _QUOTED.sub(lambda matched: " " * len(matched[0]), context.effective_query)
    clauses = _clauses(text)
    id_handoffs = {clause for clause in clauses if _ORDER_ID_WAIT.fullmatch(clause)}
    signals = [
        signal.model_copy(
            update={
                "quote": quote,
                "category": "constraint" if _PRESENTATION.fullmatch(quote) else signal.category,
            }
        )
        for signal in suggestions
        if (quote := signal.quote.strip(" ，,。；;！!？?\n"))
        and raw.count(quote) == 1
        and quote in text
    ]
    actions = [signal for signal in signals if signal.category == "action"]
    background = {
        signal.quote
        for signal in signals
        if signal.category == "background"
        and _background_boundary(signal.quote, text, clauses)
        and not any(action.quote in signal.quote for action in actions)
        and not _CONDITIONAL.search(signal.quote)
        and not _NEGATIVE.search(signal.quote)
        and not any(pattern.search(signal.quote) for pattern in _WRITE_PATTERNS.values())
        and not _affirmative_request(signal.quote, text)
        and not (
            (user_orders(signal.quote) or SKU_RE.search(signal.quote))
            and _READ_REQUEST.search(signal.quote)
        )
    }
    # An explicit handoff of the required input is fulfilled by a later user turn.
    # Keeping it as a business predicate would stop the same read after receiving its ID.
    background.update(id_handoffs)
    if (
        context
        and context.focus_quote
        and not _clause_goals(context.focus_quote, order=False, product=False)
        and not any(
            signal.quote in context.focus_quote
            for signal in signals
            if signal.category in {"action", "unresolved", "dependency"}
        )
    ):
        background.add(context.focus_quote)
    entity_text = text
    for clause in background:
        text = text.replace(clause, " " * len(clause), 1)
        if _ILLUSTRATION.search(clause):
            entity_text = entity_text.replace(clause, " " * len(clause), 1)
    coherent = [
        signal.quote
        for signal in signals
        if signal.category in {"action", "field"} and _COORDINATION.search(signal.quote)
    ]
    dependencies = tuple(
        signal.quote
        for signal in signals
        if signal.category == "dependency" and signal.quote not in id_handoffs
    )
    if not dependencies:
        dependencies = tuple(clause for clause in _clauses(text) if _TASK_LINK.search(clause))
    # A source-grounded pair may block execution even without a verified predicate.
    # Only bind_payment_dependency can grant permission to execute a conditional read.
    dependencies += tuple(
        hint.condition_quote
        for hint in dependency_hints
        if hint.condition_quote.strip()
        and hint.action_quote.strip()
        and raw.count(hint.condition_quote) == raw.count(hint.action_quote) == 1
        and hint.condition_quote not in hint.action_quote
        and hint.action_quote not in hint.condition_quote
        and not _PRESENTATION.fullmatch(hint.condition_quote)
        and hint.condition_quote not in id_handoffs
    )
    constraints = tuple(signal.quote for signal in signals if signal.category == "constraint")
    standalone = {part.strip() for part in _SENTENCE.split(text)}
    independent = {
        signal.quote: signal
        for signal in signals
        if signal.category == "unresolved"
        and signal.operation == "read"
        and signal.independent
        and signal.quote in standalone
        and not _CONDITIONAL.search(text)
        and not dependencies
        and _READ_ACTION.search(signal.quote)
        and not _NEGATIVE.search(signal.quote)
        and not any(pattern.search(signal.quote) for pattern in _WRITE_PATTERNS.values())
        and not any(
            _READ_REQUEST.search(tail) or _clause_goals(tail, order=False, product=False)
            for tail in _clauses(signal.quote)[1:]
        )
    }
    goals = _resolve_lexical_goals(text, context, actions, coherent, entity_text, independent)
    attached = _apply_field_signals(goals, signals)
    covered = attached | {quote for quote in constraints if not _affirmative_request(quote, raw)}
    scoped = [
        goal.model_copy(
            update={
                "conditions": tuple(dict.fromkeys((*goal.conditions, *dependencies))),
                "constraints": tuple(dict.fromkeys((*goal.constraints, *constraints))),
                "negated": goal.negated
                or any(
                    signal.category == "constraint"
                    and signal.negated
                    and signal.kind == goal.kind
                    and signal.quote in goal.request_text
                    and (
                        _NEGATIVE.search(goal.request_text)
                        or (
                            goal.operation == "read"
                            and not _affirmative_request(goal.request_text, text)
                        )
                    )
                    for signal in signals
                ),
            }
        )
        for goal in goals
        if not (
            goal.kind == G.UNKNOWN
            and not goal.negated
            and not goal.conditions
            and goal.request_text in covered
        )
    ]
    return bind_payment_dependency(
        raw,
        scoped if dependencies else _preserve_explicit_reads(raw, scoped, signals),
        dependency_hints,
    )
