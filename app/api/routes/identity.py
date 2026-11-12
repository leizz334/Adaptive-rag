"""Read the server-verified principal without exposing credential material."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container, get_principal
from app.core.auth import Principal
from app.core.exceptions import ToolPermissionError
from app.services.container import AppContainer

router = APIRouter(tags=["identity"])


@router.get("/auth/me")
async def self_principal(
    principal: Annotated[Principal | None, Depends(get_principal)],
    container: AppContainer = Depends(get_container),
):
    if principal is None:
        raise ToolPermissionError("verified identity required")
    await container.chat_service._enforce_rate_limit(principal.subject)
    return dict(subject=principal.subject, roles=sorted(principal.roles))
