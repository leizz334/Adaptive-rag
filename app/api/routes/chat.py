"""Chat routes: single-shot JSON and SSE streaming."""

from contextlib import aclosing

from anyio import CancelScope
from fastapi import APIRouter, Depends, Request
from sse_starlette import JSONServerSentEvent
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_container
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.container import AppContainer

router = APIRouter(tags=["chat"])


class ClosingEventSourceResponse(EventSourceResponse):
    """Explicitly close nested iterators when ASGI disconnects during send."""

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with CancelScope(shield=True):
                await self.body_iterator.aclose()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> ChatResponse:
    """Answer one turn and return the full JSON response."""
    return await container.chat_service.chat(payload, trace_id=request.state.trace_id)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    container: AppContainer = Depends(get_container),
) -> EventSourceResponse:
    """Answer one turn as an SSE stream of node, token and answer events."""

    async def events():
        async with aclosing(
            container.chat_service.stream(payload, trace_id=request.state.trace_id)
        ) as stream:
            async for item in stream:
                yield JSONServerSentEvent(item)

    return ClosingEventSourceResponse(events())
