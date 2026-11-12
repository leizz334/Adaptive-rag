"""Authenticated inspection and durable pending-approval cancellation."""

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.dependencies import get_container, get_principal
from app.core.auth import Principal
from app.core.exceptions import ToolPermissionError
from app.core.request_scope import request_session
from app.core.time import utcnow
from app.repositories.models import IdempotencyRow, MessageRow, PendingConfirmationRow, SessionRow
from app.services.container import AppContainer

router = APIRouter(tags=["workbench"])


async def workbench_access(
    principal: Annotated[Principal | None, Depends(get_principal)],
    container: AppContainer = Depends(get_container),
):
    if principal is None:
        raise ToolPermissionError("verified identity required")
    await container.chat_service._enforce_rate_limit(principal.subject)
    return principal, container


Access = Annotated[tuple, Depends(workbench_access)]


async def owned_session(db, session_id, subject):
    row = await db.get(SessionRow, session_id)
    if row is None or row.user_id != subject:
        raise HTTPException(404, "not found")


@router.get("/sessions/{session_id}/traces/{root_run_id}")
async def trace(session_id: str, root_run_id: str, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        await owned_session(db, session_id, principal.subject)
        snapshot = container.chat_service.workbench_store.get(
            root_run_id, principal.subject, session_id
        )
        if snapshot is None:
            raise HTTPException(404, "not found")
        return snapshot


async def pending_row(db, session_id, action_id, subject):
    await owned_session(db, session_id, subject)
    row = await db.scalar(
        select(PendingConfirmationRow)
        .where(PendingConfirmationRow.action_id == action_id)
        .with_for_update()
    )
    if row is None or row.session_id != session_id or row.user_id != subject:
        raise HTTPException(404, "not found")
    return row


@router.get("/sessions/{session_id}/actions/{action_id}")
async def action_status(session_id: str, action_id: str, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        row = await pending_row(db, session_id, action_id, principal.subject)
        completed = await db.get(IdempotencyRow, action_id) is not None
        return dict(
            action_id=action_id,
            status="completed"
            if completed
            else "expired"
            if row.expires_at.replace(tzinfo=UTC) <= utcnow()
            else "pending",
            expires_at=row.expires_at.replace(tzinfo=UTC).isoformat(),
        )


@router.post("/sessions/{session_id}/actions/{action_id}/cancel")
async def cancel_action(session_id: str, action_id: str, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        row = await pending_row(db, session_id, action_id, principal.subject)
        if await db.get(IdempotencyRow, action_id) is not None:
            raise HTTPException(409, "action already completed")
        if row.expires_at.replace(tzinfo=UTC) <= utcnow():
            raise HTTPException(409, "action expired")
        await db.delete(row)
        await db.commit()
    return dict(action_id=action_id, status="cancelled")


@router.get("/sessions")
async def list_sessions(access: Access):
    principal, container = access
    first_user = (
        select(MessageRow.content)
        .where(MessageRow.session_id == SessionRow.session_id, MessageRow.role == "user")
        .order_by(MessageRow.id)
        .limit(1)
        .correlate(SessionRow)
        .scalar_subquery()
    )
    async with request_session(container.session_factory) as db:
        rows = await db.execute(
            select(SessionRow.session_id, SessionRow.updated_at, first_user.label("title"))
            .where(SessionRow.user_id == principal.subject)
            .order_by(SessionRow.updated_at.desc(), SessionRow.session_id)
            .limit(50)
        )
        return {
            "sessions": [
                dict(
                    session_id=row.session_id,
                    title=(row.title or "空对话")[:80],
                    updated_at=row.updated_at.replace(tzinfo=UTC).isoformat(),
                )
                for row in rows
            ]
        }


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        await owned_session(db, session_id, principal.subject)
        rows = list(
            await db.scalars(
                select(MessageRow)
                .where(
                    MessageRow.session_id == session_id, MessageRow.role.in_(["user", "assistant"])
                )
                .order_by(MessageRow.id.desc())
                .limit(101)
            )
        )
        return {
            "messages": [
                dict(
                    id=str(row.id),
                    role=row.role,
                    content=row.content,
                    created_at=row.created_at.replace(tzinfo=UTC).isoformat(),
                )
                for row in reversed(rows[:100])
            ],
            "truncated": len(rows) > 100,
        }
