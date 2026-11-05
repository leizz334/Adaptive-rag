"""Selective, untrusted session context. Entity hints never grant authority."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.config.settings import Settings
from app.core.exceptions import GuardrailError
from app.guardrails.injection import detect_prompt_injection
from app.schemas.chat import ChatMessage

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


def user_orders(text: str) -> list[str]:
    try:
        detect_prompt_injection(text)
    except GuardrailError:
        return []
    return list(dict.fromkeys(m.upper() for m in ORDER_PATTERN.findall(text)))


@dataclass(frozen=True)
class SelectedContext:
    effective_query: str
    order_id: str | None = None
    needs_clarification: bool = False
    history: tuple[str, ...] = ()
    source: str = "none"
    summary: str = ""
    max_chars: int = 1800
    order_ids: tuple[str, ...] = ()
    original_query: str = ""
    owner_user_id: str | None = None
    session_id: str | None = None

    def prompt_context(self, stage: str) -> str:
        targets = self.order_ids or ((self.order_id,) if self.order_id else ())
        if not targets or stage not in {"planner", "generate"}:
            return ""
        value: dict = {
            "order_reference": self.order_id,
            "source": self.source,
            "authority": "untrusted_reference_only; use current tools and permissions",
        }
        if len(targets) > 1:
            value["order_references"] = targets
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
                value = {"order_reference": self.order_id or targets, "source": self.source}
                break
        return json.dumps(value, ensure_ascii=False)


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
    ) -> SelectedContext:
        if self.settings.memory_mode == "M0":
            return SelectedContext(query, original_query=query)
        direct = user_orders(query)
        order_anaphora = bool(
            re.search(r"(?:这|那|该)(?:一)?(?:张|笔|份|个)?(?:订单|单子|单)", query)
        )
        first_reference = any(
            cue in query for cue in ("第一次", "最先提到", "最初提到", "第一笔", "第一张")
        )
        reference = any(cue in query for cue in REFERENCE_CUES) or order_anaphora or first_reference
        pointed_order = order_anaphora or any(
            cue in query
            for cue in (
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
        )
        general_policy = any(
            cue in query
            for cue in ("规则", "政策", "条件", "怎么算", "通用", "一般", "有哪些", "什么是")
        )
        if not direct and general_policy and not pointed_order:
            return SelectedContext(query)
        if (
            not direct
            and not pointed_order
            and not any(
                cue in query
                for cue in (
                    "订单",
                    "状态",
                    "发货",
                    "物流",
                    "进度",
                    "取消",
                    "运单",
                    "支付",
                    "付款",
                    "金额",
                    "快递",
                    "包裹",
                )
            )
        ):
            return SelectedContext(query)
        # Specific business follow-ups can omit both the identifier and a
        # pronoun. General policy/social questions were excluded above.
        if not direct and not reference:
            reference = any(
                cue in query
                for cue in (
                    "再",
                    "重新",
                    "现在",
                    "目前",
                    "最新",
                    "此刻",
                    "付款",
                    "支付",
                    "订单状态",
                )
            )
            if not reference:
                return SelectedContext(query)
        recent = history[-self.settings.memory_recent_messages :]
        candidates = direct
        source = "current_user" if direct else "none"
        joint_read = (
            len(direct) > 1
            and any(
                cue in query for cue in ("分别", "比较", "对比", "都要看", "都要核对", "两笔都")
            )
            and not any(cue in query for cue in ("取消", "申请退款", "申请退货", "不要操作"))
        )
        if joint_read:
            return SelectedContext(
                query,
                source=source,
                order_ids=tuple(direct),
                original_query=query,
                max_chars=self.settings.memory_context_max_chars,
            )
        if not candidates and reference:
            if first_reference:
                chronological = list(
                    dict.fromkeys(
                        order
                        for message in recent
                        if message.role == "user"
                        for order in user_orders(message.content)
                    )
                )
                if chronological:
                    candidates = chronological[:1]
                    source = "session_user_explicit_ordinal"
            for message in reversed(recent):
                if not candidates and message.role == "user":
                    candidates = user_orders(message.content)
                    if candidates:
                        source = "session_user"
                        break
            if not candidates and self.settings.memory_mode in {"M2", "M3"}:
                candidates = summary_orders or []
                source = "session_summary_user_entity" if candidates else "none"
        if len(candidates) != 1:
            return SelectedContext(query, needs_clarification=True, original_query=query)
        order_id = candidates[0]
        selected = tuple(
            m.content[:240] for m in recent if m.role == "user" and user_orders(m.content)
        )[-2:]
        effective = query if direct else f"{query}（会话指代：订单 {order_id}，状态须实时查询）"
        return SelectedContext(
            effective,
            order_id,
            history=selected,
            source=source,
            summary=summary[: self.settings.memory_context_max_chars],
            max_chars=self.settings.memory_context_max_chars,
            order_ids=(order_id,),
            original_query=query,
        )


def node_query(state) -> str:
    return state.get("resolved_query") or state["user_query"]


def node_context(state, stage: str) -> str:
    context = state.get("selected_context")
    return context.prompt_context(stage) if context else ""
