"""Owner-bound incremental summaries stored in the existing SessionRow.summary column."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config.settings import Settings
from app.memory.context import user_orders
from app.memory.summarizer import ConversationSummarizer
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatMessage


class SummaryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    session_id: str
    owner_id: str
    revision: int = Field(default=0, ge=0)
    coverage_message_id: int = Field(default=0, ge=0)
    source_message_id: int = Field(default=0, ge=0)
    order_ids: list[str] = Field(default_factory=list, max_length=2)
    text: str = ""
    expires_at: float

    @classmethod
    def restore(cls, text: str, *, session_id: str, owner_id: str, latest_id: int):
        try:
            value = cls.model_validate_json(text)
        except (ValidationError, ValueError, TypeError):
            return None
        if (
            value.session_id != session_id
            or value.owner_id != owner_id
            or value.expires_at <= time.time()
            or value.coverage_message_id > latest_id
            or value.source_message_id > value.coverage_message_id
        ):
            return None
        return value


async def prepare_summary(repo: SessionRepository, row, settings: Settings):
    recent = await repo.recent_message_rows(row.session_id, limit=settings.memory_recent_messages)
    history = [ChatMessage.model_validate({"role": r.role, "content": r.content}) for r in recent]
    latest = recent[-1].id if recent else 0
    summary = SummaryEnvelope.restore(
        row.summary or "", session_id=row.session_id, owner_id=row.user_id, latest_id=latest
    )
    if summary and summary.order_ids:
        source = await repo.message_by_id(row.session_id, summary.source_message_id)
        if (
            source is None
            or source.role != "user"
            or user_orders(source.content)[:2] != summary.order_ids
        ):
            summary = None
    if summary is None:
        summary = SummaryEnvelope(
            session_id=row.session_id,
            owner_id=row.user_id,
            expires_at=time.time() + settings.memory_summary_ttl_seconds,
        )
    advanced = False
    while True:
        older = await repo.messages_since(
            row.session_id,
            after=summary.coverage_message_id,
            before=recent[0].id if recent else 0,
            limit=200,
        )
        if not older:
            break
        for message in older:
            if message.role == "user":
                orders = user_orders(message.content)
                if orders:
                    summary.order_ids = orders[:2]
                    summary.source_message_id = message.id
        summary.text = ConversationSummarizer.merge_extractively(
            summary.text,
            [ChatMessage.model_validate({"role": r.role, "content": r.content}) for r in older],
            max_chars=settings.memory_context_max_chars,
        )
        summary.coverage_message_id = older[-1].id
        advanced = True
        if len(older) < 200:
            break
    if advanced:
        summary.revision += 1
        summary.expires_at = time.time() + settings.memory_summary_ttl_seconds
    encoded = summary.model_dump_json() if summary.coverage_message_id else ""
    return history, encoded, summary.order_ids, summary.text
