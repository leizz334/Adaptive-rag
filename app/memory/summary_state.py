"""Owner-bound incremental summaries stored in the existing SessionRow.summary column."""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.state import AgentState
from app.config.settings import Settings
from app.memory.context import user_orders
from app.memory.summarizer import ConversationSummarizer
from app.memory.task_memory import (
    MAX_TASKS,
    TaskRecord,
    TaskSource,
    merge_records,
    restore_source,
    task_record,
)
from app.repositories.models import MessageRow, SessionRow
from app.repositories.session_repository import SessionRepository
from app.schemas.chat import ChatMessage


class SummaryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1, 2] = 1
    session_id: str
    owner_id: str
    revision: int = Field(default=0, ge=0)
    coverage_message_id: int = Field(default=0, ge=0)
    source_message_id: int = Field(default=0, ge=0)
    order_ids: list[str] = Field(default_factory=list, max_length=2)
    text: str = ""
    expires_at: float
    tasks: list[TaskRecord] = Field(default_factory=list, max_length=MAX_TASKS)

    @classmethod
    def restore(cls, text: str, *, session_id: str, owner_id: str, latest_id: int):
        if len(text) > 256_000:
            return None
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


def _restore(text: str, row: SessionRow, latest: int) -> SummaryEnvelope | None:
    return SummaryEnvelope.restore(
        text, session_id=row.session_id, owner_id=row.user_id, latest_id=latest
    )


def _new(row: SessionRow, settings: Settings) -> SummaryEnvelope:
    return SummaryEnvelope(
        session_id=row.session_id,
        owner_id=row.user_id,
        expires_at=time.time() + settings.memory_summary_ttl_seconds,
    )


async def prepare_summary(repo: SessionRepository, row, settings: Settings):
    recent = await repo.recent_message_rows(row.session_id, limit=settings.memory_recent_messages)
    history = [ChatMessage.model_validate({"role": r.role, "content": r.content}) for r in recent]
    latest = recent[-1].id if recent else 0
    summary = _restore(row.summary or "", row, latest)
    if summary and summary.order_ids:
        source = await repo.message_by_id(row.session_id, summary.source_message_id)
        if (
            source is None
            or source.role != "user"
            or user_orders(source.content)[:2] != summary.order_ids
        ):
            summary = None
    if summary is None:
        summary = _new(row, settings)
    structured = settings.memory_mode == "M2"
    sources: dict[int, TaskSource] = {}
    if structured:
        if summary.version == 1 and summary.coverage_message_id:
            # The old cursor covers excerpts, not the typed task index.
            summary.coverage_message_id = 0
            summary.source_message_id = 0
            summary.order_ids = []
        rows = {
            message.id: message
            for message in await repo.source_messages(
                row.session_id, [record.message_id for record in summary.tasks]
            )
        }
        for record in summary.tasks:
            source = rows.get(record.message_id)
            if source and (
                valid := restore_source(record, source, settings.memory_summary_ttl_seconds)
            ):
                sources[source.id] = valid
        summary.tasks = [source.record for source in sources.values()]
        summary.version = 2
        summary.text = ""
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
                if structured and message.id not in sources and (archived := task_record(message)):
                    if valid := restore_source(
                        archived, message, settings.memory_summary_ttl_seconds
                    ):
                        sources[message.id] = valid
        if structured:
            summary.tasks = merge_records([source.record for source in sources.values()])
            sources = {record.message_id: sources[record.message_id] for record in summary.tasks}
        else:
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
    if structured:
        for message in recent:
            if message.id not in sources and (recent_record := task_record(message)):
                if valid := restore_source(
                    recent_record, message, settings.memory_summary_ttl_seconds
                ):
                    sources[message.id] = valid
    encoded = summary.model_dump_json() if summary.coverage_message_id or summary.tasks else ""
    return history, encoded, summary.order_ids, summary.text, tuple(sources.values())


async def record_completed_turn(
    repo: SessionRepository,
    row: SessionRow,
    message: MessageRow,
    prepared: str,
    state: AgentState,
    settings: Settings,
) -> None:
    """Merge the version prepared before inference with the owner-locked current version."""
    existing = _restore(row.summary or "", row, message.id)
    if existing and existing.version != 2:
        existing = None
    candidate = _restore(prepared, row, message.id)
    if existing and existing.tasks:
        rows = {
            item.id: item
            for item in await repo.source_messages(
                row.session_id, [task.message_id for task in existing.tasks]
            )
        }
        existing.tasks = [
            task
            for task in existing.tasks
            if (source := rows.get(task.message_id))
            and restore_source(task, source, settings.memory_summary_ttl_seconds)
        ]
    versions = [item for item in (existing, candidate) if item]
    summary = max(
        versions, key=lambda item: (item.coverage_message_id, item.revision), default=None
    )
    summary = summary or _new(row, settings)
    summary.version = 2
    summary.text = ""
    new = task_record(message, state)
    summary.tasks = merge_records(*(version.tasks for version in versions), [new] if new else [])
    row.summary = summary.model_dump_json()
