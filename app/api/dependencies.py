"""FastAPI dependency providers."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.auth import Principal, bind_identity
from app.schemas.chat import ChatRequest
from app.services.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_principal(request: Request) -> Principal | None:
    return request.app.state.authenticator.authenticate(request.headers.getlist("authorization"))


def authenticated_payload(
    payload: ChatRequest, principal: Annotated[Principal | None, Depends(get_principal)]
) -> ChatRequest:
    return bind_identity(payload, principal)
