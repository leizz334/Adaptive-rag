"""Selective, untrusted session context. Entity hints never grant authority."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.config.settings import Settings
from app.core.exceptions import GuardrailError
from app.guardrails.injection import detect_prompt_injection
from app.memory.budget import estimate_tokens
from app.observability.tracing import span
from app.schemas.chat import ChatMessage
from app.schemas.goals import EntitySource, TaskGoal

if TYPE_CHECKING:
    from app.memory.task_memory import TaskSource

ORDER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])ORD\d+(?![A-Za-z0-9_])", re.I)
REFERENCE_CUES = (
    "它",
    "这单",
    "那单",
    "该订单",
    "刚才",
    "之前",
    "前面",
    "上一个",
    "同一笔",
    "上一笔",
    "这笔",
    "那笔",
    "那个订单",
    "这个订单",
    "刚查的",
    "刚看的",
)
_POINTED_ORDER_CUES = (
    "它",
    "这单",
    "那单",
    "该订单",
    "同一笔",
    "上一笔",
    "这笔",
    "那笔",
    "那个订单",
    "这个订单",
)
_REFERENCE_SUBJECT = re.compile(r"^(?:" + "|".join(_POINTED_ORDER_CUES) + r")(?:的)?[，,]?")
_REFERENCE_TIME_PREFIX = re.compile(r"^(?:现在|目前|接下来)[，,]?")
_LOOKUP_VERB = r"(?:查询|查看|查一下|看一下|看下|查|看)"
_ORDER_TASK_TERMS = (
    "订单",
    "状态",
    "进度",
    "查询",
    "查一下",
    "发货",
    "物流",
    "快递",
    "运单",
    "支付",
    "金额",
    "实付",
)
_READ_PREFIX = re.compile(r"^(?:请问|麻烦|请|帮我|看一下|看下|查一下|确认一下|[，,])+")
_ACKNOWLEDGEMENT = re.compile(r"(?:嗯|好(?:的)?|行|明白了|知道了|谢谢(?:你)?|收到|[，,。！!])+")
_READ_ORDER_QUESTION = re.compile(
    r"(?:(?:现在|目前|已经|刚刚|预计|大概|到底))*"
    r"(?:"
    r"(?:有|没有|是否)?(?:发货|发走|发出|发|出库|寄出|寄|签收|送达|到货|支付|付款|扣款)"
    r"(?:成功|了|过)?(?:吗|么|没有|没|呢|呀|啊)?"
    r"|(?:什么(?:时候|时间)|哪(?:天|一天)|几(?:号|点|时))"
    r"(?:能|会|可以)?(?:到(?:货|达)?|送到|送达|收到|发货|出库|寄出)"
    r"|(?:(?:一共|总共|实付|应付|付了|金额是|总价是))?多少(?:钱|元)?(?:了|来着|呢|呀|啊|吗)?"
    r"|(?:运单|快递单|物流单)号(?:是(?:多少|什么)|(?:有|出来)(?:了)?(?:吗|没有|没)?)"
    r"|(?:物流|快递|包裹)?(?:到哪(?:里|儿)?(?:了)?|走到哪(?:里|儿)?了)"
    r"|(?:物流|快递|包裹)有更新(?:了吗|吗)?"
    r"|(?:状态|进度)(?:怎么样(?:了)?|如何|有(?:更新|变化)(?:了吗|吗)?)"
    r"|(?:是)?什么(?:订单)?状态"
    r")"
)
_QUESTION_SIGNAL = re.compile(r"[？?吗么呢]|没有$|没$|什么|哪|几|多少|如何|是否")
_ORDER_NUMBER_ONLY = re.compile(r"(?:我的)?(?:(?:订单号|单号|订单)(?:是|[：:])?)?ORD\d+", re.I)
_READ_FIELD = r"(?:订单状态|状态|物流(?:轨迹)?|快递|运单号|付款状态|支付状态|实付金额|订单金额)"
_READ_FIELD_REQUEST = re.compile(
    rf"(?:{_LOOKUP_VERB}(?:(?:它|这单|那单)(?:的)?)?{_READ_FIELD}"
    rf"|{_READ_FIELD}(?:再)?(?:帮我)?(?:再)?(?:确认|核对|复核|查|看)(?:一下|一遍|一次)?"
    rf"|把(?:这|那)(?:笔|单)(?:的)?{_READ_FIELD}(?:告诉我|给我))"
)
_ORDER_ID = r"ORD\d+(?![A-Za-z0-9_])"
_ORDER_CORRECTION = re.compile(
    rf"^(?:不是\s*(?:订单\s*)?(?P<rejected>{_ORDER_ID})\s*[，,、]\s*"
    r"|(?:刚才)?(?:的)?(?:订单号|单号)(?:报|说|写|填|发)错了[，,：:]\s*)"
    rf"(?:应该是|应为|更正为|是)\s*(?:订单\s*)?(?P<target>{_ORDER_ID})",
    re.I,
)
_ORDER_FOCUS = re.compile(
    rf"^(?:现在|接下来|接着|然后|暂时|这次)?(?:只(?:查|看|关注|跟踪)|改(?:查|看|为查询)|换成)"
    rf"\s*(?:订单\s*)?(?P<target>{_ORDER_ID})",
    re.I,
)
_EXCLUDED_ORDER = re.compile(
    rf"[，,]\s*(?:先)?(?:不查|不用查|不要查)\s*(?:订单\s*)?(?P<excluded>{_ORDER_ID})[。！!]*$",
    re.I,
)
_TASK_REFERENCE = re.compile(
    r"^(?:刚才|之前|前面)(?:查|问)(?:过)?"
    r"(?P<topic>物流|快递|付款(?:状态)?|支付(?:状态)?|实付(?:金额)?|订单金额)"
    r"(?:的)?(?:那笔订单|那个订单|那张订单|那单|那笔)(?:的)?[，,]?"
)
_HISTORY_TOPICS = {
    "shipping": re.compile(r"物流|快递|运单|发货|签收|出库|寄出"),
    "payment": re.compile(r"支付|付款|扣款"),
    "amount": re.compile(r"实付|订单金额|总价|多少钱"),
}
_NON_ASSERTED_TASK = re.compile(r"别查|不要|不用|无需|不必|不查|没查|如果|例如|比如|举例|示例")
_CONTINUE = re.compile(r"回到|继续|接着|按之前|同上")
_EXPLICIT_ORDER_REFERENCE = re.compile(r"(?:这|那)(?:张|笔)(?:订单|单)|(?:这|那)单")
_PRODUCT_REFERENCE = re.compile(r"(?:这|那)(?:款|件|个商品)|它")
_PRODUCT_READ = re.compile(
    r"价格|售价|多少钱|库存|存货|现货|有货|剩(?:下)?(?:几|多少)|参数|规格|详情"
)
_TOPIC_ANCHOR = re.compile(
    r"^回到(?:之前|前面|刚才)(?:聊的|问的|看的|查的)?"
    r"(?:这|那)(?:款[^，。；！？?!]{0,16}|(?:张|笔)[^，。；！？?!]{0,16}(?:单|订单))$"
)


def user_orders(text: str) -> list[str]:
    try:
        detect_prompt_injection(text)
    except GuardrailError:
        return []
    return list(dict.fromkeys(m.upper() for m in ORDER_PATTERN.findall(text)))


def _read_order_question(query: str) -> bool:
    """Recognize a single read request, without interpreting mixed or policy clauses."""
    compact = re.sub(r"\s+", "", query).strip("。！？!?～~")
    body = _READ_PREFIX.sub("", compact)
    return bool(_READ_ORDER_QUESTION.fullmatch(body) and _QUESTION_SIGNAL.search(query))


def _read_with_target(query: str) -> bool:
    compact = re.sub(r"\s+", "", query).strip("。！？!?～~")
    return _read_order_question(query) or bool(_READ_FIELD_REQUEST.fullmatch(compact))


def _named_reference(query: str) -> tuple[bool, str | None]:
    compact = _REFERENCE_TIME_PREFIX.sub("", re.sub(r"\s+", "", query))
    prefix = _READ_PREFIX.match(compact)
    body = compact[prefix.end() :] if prefix else compact
    task = _TASK_REFERENCE.match(body)
    if task and _read_with_target(body[task.end() :]):
        return True, next(
            name for name, pattern in _HISTORY_TOPICS.items() if pattern.search(task["topic"])
        )
    reference = _REFERENCE_SUBJECT.match(body)
    if not reference or body.startswith("上一笔"):
        return False, None
    tail = body[reference.end() :]
    field_request = (
        prefix
        and re.search(_LOOKUP_VERB, prefix[0])
        and re.fullmatch(_READ_FIELD, tail.rstrip("。！？!?"))
    )
    return bool(field_request or _read_with_target(tail)), None


def _order_correction(text: str) -> re.Match[str] | None:
    match = _ORDER_CORRECTION.match(text.strip())
    if match:
        tail = text.strip()[match.end() :].lstrip("的，,、：:。；; ").strip("。！!")
        if (match["rejected"] or "").upper() != match["target"].upper() and (
            not tail or _read_with_target(tail)
        ):
            return match
    return None


def _read_focus(text: str) -> str | None:
    text = text.strip()
    focus = _ORDER_FOCUS.match(text)
    if not focus:
        return None
    exclusion = _EXCLUDED_ORDER.search(text, focus.end())
    if exclusion and exclusion["excluded"].upper() == focus["target"].upper():
        return None
    positive = text[: exclusion.start()] if exclusion else text
    tail = positive[focus.end() :].strip("的，,、：: 。！!")
    if not tail or re.fullmatch(_READ_FIELD, tail) or _read_with_target(tail):
        return positive
    return None


def _focused_order(text: str, orders: list[str], *, allow_switch: bool = True) -> str | None:
    correction = _order_correction(text)
    if correction and correction["target"].upper() in orders:
        return correction["target"].upper()
    if allow_switch and (focus := _read_focus(text)):
        selected = user_orders(focus)
        if len(selected) == 1:
            return selected[0]
    return None


def _recent_read_history(recent: list[ChatMessage]) -> list[ChatMessage]:
    active = []
    for message in reversed(recent):
        if message.role != "user":
            continue
        text = message.content.strip()
        orders = user_orders(text)
        if orders and (
            _ORDER_NUMBER_ONLY.fullmatch(re.sub(r"\s+", "", text).rstrip("。！!"))
            or _focused_order(text, orders)
            or (
                any(term in text for term in _ORDER_TASK_TERMS)
                and not _NON_ASSERTED_TASK.search(text)
                and not any(
                    term in text
                    for term in ("例如", "比如", "示例", "举例", "一般", "政策", "规则")
                )
            )
        ):
            active.append(message)
        elif not (
            _ACKNOWLEDGEMENT.fullmatch(text)
            or _read_order_question(text)
            or _named_reference(text)[0]
        ):
            # A subject change ends the context available to an unqualified follow-up.
            break
    return active[::-1]


def _reference_candidates(
    recent: list[ChatMessage], summary_orders: list[str], *, read: bool, task: str | None = None
) -> tuple[list[str], str]:
    candidates = dict.fromkeys(summary_orders, False)
    from_user: set[str] = set()
    for message in recent:
        if message.role != "user" or not (orders := user_orders(message.content)):
            continue
        inherited_topic = False
        if read and (focus := _focused_order(message.content, orders, allow_switch=task is None)):
            correction = _order_correction(message.content) if task else None
            if correction and correction["rejected"]:
                rejected = correction["rejected"].upper()
                inherited_topic = candidates.pop(rejected, False)
                from_user.discard(rejected)
            else:
                # A new focus supersedes earlier candidates. Independent mentions after it
                # are considered again, and a named task can use pre-focus evidence.
                candidates.clear()
                from_user.clear()
            orders = [focus]
        topic_matches = bool(
            task is not None
            and len(orders) == 1
            and _HISTORY_TOPICS[task].search(message.content)
            and not _NON_ASSERTED_TASK.search(message.content)
        )
        for order in orders:
            candidates[order] = topic_matches or inherited_topic or candidates.get(order, False)
        from_user.update(orders)
    matches = [
        order for order, topic_matches in candidates.items() if task is None or topic_matches
    ]
    source = (
        "session_user"
        if any(order in from_user for order in matches)
        else "session_summary_user_entity"
    )
    return matches, source if matches else "none"


@dataclass(frozen=True)
class SelectedContext:
    effective_query: str
    order_id: str | None = None
    needs_clarification: bool = False
    history: tuple[str, ...] = ()
    source: str = "none"
    summary: str = ""
    max_chars: int = 1800
    structured: bool = False
    product_sku: str | None = None
    product_name: str | None = None
    product_source: EntitySource = "none"
    resumed_goal: TaskGoal | None = None
    resumed_from: int | None = None
    clarification: str | None = None
    context_budget: int = 0
    focus_quote: str = ""

    def prompt_context(self, stage: str) -> str:
        if self.structured:
            return self._task_view(stage)
        if not self.order_id or stage not in {"planner", "generate"}:
            return ""
        value: dict = {
            "order_reference": self.order_id,
            "source": self.source,
            "authority": "untrusted_reference_only; use current tools and permissions",
        }
        if stage == "generate":
            value["selected_user_history"] = self.history
            if self.summary:
                value["untrusted_summary"] = self.summary
        while len(json.dumps(value, ensure_ascii=False)) > self.max_chars:
            if value.get("selected_user_history"):
                value["selected_user_history"] = value["selected_user_history"][1:]
            elif value.get("untrusted_summary"):
                value["untrusted_summary"] = value["untrusted_summary"][:-64]
            else:
                value = {"order_reference": self.order_id, "source": self.source}
                break
        return json.dumps(value, ensure_ascii=False)

    def _task_view(self, stage: str) -> str:
        if stage not in {"intent", "planner", "generate"} or self.needs_clarification:
            return ""
        parts: list[tuple[str, object]] = []
        refs: dict[str, str] = {}
        if self.order_id and self.source != "current_user":
            refs.update(order=self.order_id, source=self.source)
        if product := self.product_sku or self.product_name:
            refs.update(product=product, source=self.product_source)
        if refs and stage != "generate":
            parts.append(("entity", refs))
        if self.resumed_goal:
            goal = self.resumed_goal
            parts.append(
                (
                    "task",
                    {
                        "kind": goal.kind.value,
                        "fields": goal.fields,
                        "constraints": goal.constraints,
                        "source": goal.entity_source,
                    },
                )
            )
        if stage == "intent":
            parts.extend(("history", quote) for quote in self.history)
        used: list[tuple[str, object]] = []
        text = ""
        for section, value in parts:
            trial = json.dumps([*used, (section, value)], ensure_ascii=False, separators=(",", ":"))
            if estimate_tokens(trial) <= self.context_budget:
                used.append((section, value))
                text = trial
        trace_context(stage, text, tuple(section for section, _ in used), len(parts))
        return text


def trace_context(
    stage: str, text: str, sections: tuple[str, ...], candidates: int | None = None
) -> None:
    node = {"generate": "answer"}.get(stage, stage)
    count = candidates if candidates is not None else len(sections)
    with span(
        "memory.context_view",
        context_node=node,
        context_tokens=estimate_tokens(text),
        context_candidates=count,
        context_dropped=count - len(sections),
        context_sections=sections,
    ):
        pass


class ContextBuilder:
    def __init__(self, settings: Settings):
        self.settings = settings

    def build(
        self,
        query: str,
        history: list[ChatMessage],
        *,
        summary_orders: list[str] | None = None,
        summary: str = "",
        memory: Sequence[TaskSource] | None = None,
    ) -> SelectedContext:
        if self.settings.memory_mode == "M2" and memory is not None:
            return self._select_task_context(query, history, memory)
        return self._build_legacy(query, history, summary_orders=summary_orders, summary=summary)

    def _select_task_context(
        self, query: str, history: list[ChatMessage], memory: Sequence[TaskSource]
    ) -> SelectedContext:
        from app.memory.task_memory import SKU_PATTERN

        budget = max(
            0,
            min(
                estimate_tokens(" " * self.settings.memory_context_max_chars),
                self.settings.token_budget // 10,
                self.settings.token_budget - estimate_tokens(query) - 1024,
            ),
        )
        direct = user_orders(query)
        result = self._build_legacy(query, history)
        if len(direct) > 1 and result.needs_clarification:
            tail = re.split(r"(?<=[，,。；;])", query, maxsplit=1)[-1].strip()
            if (correction := _order_correction(tail)) and tail != query.strip():
                focus = tail[correction.start("target") :]
                if len(user_orders(focus)) == 1:
                    result = self._select(focus, user_orders(focus), "current_user", [], "")

        product_ref = _PRODUCT_REFERENCE.search(query) and _PRODUCT_READ.search(query)
        if (
            not direct
            and not result.order_id
            and not SKU_PATTERN.search(query)
            and product_ref
            and not _read_with_target(query)
        ):
            products = [
                source
                for source in memory
                if (source.record.product_skus or source.record.product_name)
                and not re.search(r"例如|比如|示例|举例", source.text)
            ]
            if named := [
                p for p in products if p.record.product_name and p.record.product_name in query
            ]:
                products = named
            skus = {sku for item in products for sku in item.record.product_skus}
            titles = {item.record.product_name for item in products if item.record.product_name}
            ambiguous_pronoun = bool(
                not re.search(r"(?:这|那)(?:款|件|个商品)", query)
                and any(source.record.order_ids for source in memory)
                and not named
            )
            if len(skus) == 1 and len(titles) <= 1 and not ambiguous_pronoun:
                sku = next(iter(skus))
                result = SelectedContext(
                    f"{query}（会话商品指代：{sku}，须实时查目录）",
                    product_sku=sku,
                    product_source="session_summary_user_entity",
                )
            elif not skus and len(titles) == 1 and not ambiguous_pronoun:
                title = next(iter(titles))
                result = SelectedContext(
                    f"{query}（会话商品名称候选：{title}，须实时查目录）",
                    product_name=title,
                    product_source="session_summary_user_entity",
                )
            elif products:
                result = SelectedContext(query, needs_clarification=True, clarification="product")

        order_ref = (
            _named_reference(query)[0]
            or _read_order_question(query)
            or _EXPLICIT_ORDER_REFERENCE.search(query)
            or (_CONTINUE.search(query) and any(cue in query for cue in REFERENCE_CUES))
        )
        if (
            not direct
            and not result.order_id
            and not product_ref
            and order_ref
            and not SKU_PATTERN.search(query)
        ):
            historical = [
                ChatMessage(role="user", content=item.text)
                for item in sorted(memory, key=lambda item: item.record.message_id)
                if item.record.order_ids and not re.search(r"例如|比如|示例|举例", item.text)
            ]
            _, task = _named_reference(query)
            candidates, _ = _reference_candidates(historical, [], read=True, task=task)
            if candidates:
                result = self._select(query, candidates, "session_summary_user_entity", [], "")

        result = self._resume_task(query, result, memory, budget)
        lead = re.split(r"[，,。；;]", query.strip(), maxsplit=1)[0]
        focus_quote = (
            lead
            if (
                (result.order_id or result.product_sku or result.product_name)
                and _TOPIC_ANCHOR.fullmatch(lead)
                and not _NON_ASSERTED_TASK.search(lead)
            )
            else ""
        )
        relevant = [
            source.text
            for source in memory
            if (
                (
                    result.order_id
                    and source.record.order_ids == (result.order_id,)
                    and result.source != "current_user"
                )
                or (result.product_sku and source.record.product_skus == (result.product_sku,))
                or (result.product_name and source.record.product_name == result.product_name)
                or source.record.message_id == result.resumed_from
            )
        ]
        return replace(
            result,
            history=tuple(dict.fromkeys(reversed(relevant)))[:2],
            summary="",
            structured=True,
            context_budget=budget,
            focus_quote=focus_quote,
        )

    def _resume_task(
        self, query: str, selected: SelectedContext, memory: Sequence[TaskSource], budget: int
    ) -> SelectedContext:
        from app.agents.goals import resolve_goals
        from app.memory.task_memory import resumable_goal
        from app.schemas.goals import GoalKind

        declared = user_orders(query)
        tail = re.sub(r"^(?:找到了|查到了|核对好了)[，,。\s]*", "", query.strip())
        identifier_only = len(declared) == 1 and _ORDER_NUMBER_ONLY.fullmatch(
            re.sub(r"\s+", "", tail).rstrip("。！!")
        )
        continued = bool(_CONTINUE.search(query))
        if not memory or not (identifier_only or continued):
            return selected
        source_list = sorted(memory, key=lambda source: source.record.message_id, reverse=True)
        active = (
            [source_list[0]]
            if identifier_only
            else [
                item
                for item in source_list
                if selected.order_id and item.record.order_ids == (selected.order_id,)
            ][:1]
        )
        if not active:
            return selected
        record = active[0].record
        current = [
            goal
            for goal in resolve_goals(query)
            if goal.kind != GoalKind.UNKNOWN and not goal.negated
        ]
        original = resolve_goals(active[0].text)
        if (
            continued
            and current
            and any(
                item.conditions
                and any(goal.kind == item.kind and not goal.conditions for goal in current)
                for item in original
            )
        ):
            return SelectedContext(query, needs_clarification=True, clarification="constraint")
        if current:
            return selected
        eligible = [
            item
            for item in record.goals
            if resumable_goal(item)
            and item.goal.entity_type == "order"
            and any(
                goal.kind == item.goal.kind
                and goal.operation == "read"
                and not (goal.negated or goal.conditions)
                and set(item.goal.fields).issubset(goal.fields)
                for goal in original
            )
            and (
                (identifier_only and item.status == "open" and item.goal.entity_id is None)
                or (continued and item.goal.entity_id in {None, selected.order_id})
            )
        ]
        if (
            len(eligible) != 1
            or record.pending_ref
            or any(goal.operation == "write" or goal.conditions for goal in original)
        ):
            if continued and record.protected:
                return SelectedContext(query, needs_clarification=True, clarification="constraint")
            return selected
        goal = eligible[0].goal
        if estimate_tokens(json.dumps(goal.constraints, ensure_ascii=False)) + 100 > budget:
            return SelectedContext(query, needs_clarification=True, clarification="constraint")
        if identifier_only:
            selected = self._select(query, declared, "current_user", [], "")
        if not selected.order_id or selected.needs_clarification:
            return selected
        return replace(selected, resumed_from=record.message_id, resumed_goal=goal)

    def _build_legacy(
        self,
        query: str,
        history: list[ChatMessage],
        *,
        summary_orders: list[str] | None = None,
        summary: str = "",
    ) -> SelectedContext:
        if self.settings.memory_mode == "M0":
            return SelectedContext(query)
        direct = user_orders(query)
        recent = history[-self.settings.memory_recent_messages :]
        m2 = self.settings.memory_mode == "M2"
        if m2 and len(direct) > 1:
            correction = _order_correction(query)
            target_query = (
                query.strip()[correction.start("target") :] if correction else _read_focus(query)
            )
            if target_query and len(target := user_orders(target_query)) == 1:
                return self._select(target_query, target, "current_user", recent, summary)
        if m2 and not direct and _read_order_question(query):
            active = _recent_read_history(recent)
            if not active:
                return SelectedContext(query)
            candidates, source = _reference_candidates(active, [], read=True)
            return self._select(query, candidates, source, recent, summary)
        reference = any(cue in query for cue in REFERENCE_CUES)
        pointed_order = any(cue in query for cue in _POINTED_ORDER_CUES)
        # A generic pronoun needs an order-specific predicate before it can select an order.
        if (
            m2
            and not direct
            and "它" in query
            and not any(cue != "它" and cue in query for cue in _POINTED_ORDER_CUES)
            and not _named_reference(query)[0]
            and not any(
                cue in query
                for cue in (
                    "订单",
                    "发货",
                    "物流",
                    "快递",
                    "运单",
                    "支付",
                    "付款",
                    "实付",
                    "取消",
                    "退款",
                    "退货",
                )
            )
        ):
            return SelectedContext(query)
        general_policy = any(cue in query for cue in ("规则", "政策", "条件", "怎么算"))
        if not direct and general_policy and not pointed_order:
            return SelectedContext(query)
        if (
            not direct
            and not pointed_order
            and not any(
                cue in query
                for cue in ("订单", "状态", "发货", "物流", "进度", "取消", "运单", "支付")
            )
        ):
            return SelectedContext(query)
        if not direct and not reference:
            return SelectedContext(query)
        candidates = direct
        source = "current_user" if direct else "none"
        if not candidates and reference:
            if m2:
                read, task = _named_reference(query)
                candidates, source = _reference_candidates(
                    recent, summary_orders or [], read=read, task=task
                )
                return self._select(query, candidates, source, recent, summary)
            for message in reversed(recent):
                if message.role == "user":
                    candidates = user_orders(message.content)
                    if candidates:
                        source = "session_user"
                        break
            if not candidates and self.settings.memory_mode == "M3":
                candidates = summary_orders or []
                source = "session_summary_user_entity" if candidates else "none"
        return self._select(query, candidates, source, recent, summary)

    def _select(
        self,
        query: str,
        candidates: list[str],
        source: str,
        recent: list[ChatMessage],
        summary: str,
    ) -> SelectedContext:
        if len(candidates) != 1:
            return SelectedContext(query, needs_clarification=True)
        order_id = candidates[0]
        m2 = self.settings.memory_mode == "M2"
        if m2 and any(
            mentioned.upper() != order_id for mentioned in ORDER_PATTERN.findall(summary)
        ):
            summary = ""
        selected = []
        for message in recent:
            if message.role != "user" or not (orders := user_orders(message.content)):
                continue
            if not m2 or orders == [order_id]:
                selected.append(message.content[:240])
        effective = (
            query
            if source == "current_user"
            else f"{query}（会话指代：订单 {order_id}，状态须实时查询）"
        )
        return SelectedContext(
            effective,
            order_id,
            history=tuple(selected[-2:]),
            source=source,
            summary=summary[: self.settings.memory_context_max_chars],
            max_chars=self.settings.memory_context_max_chars,
        )


def node_query(state) -> str:
    return state.get("resolved_query") or state["user_query"]


def node_context(state, stage: str) -> str:
    context = state.get("selected_context")
    return context.prompt_context(stage) if context else ""
