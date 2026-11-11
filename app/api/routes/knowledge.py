"""Private knowledge API: subject comes exclusively from the Bearer verifier."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_container, get_principal
from app.core.auth import Principal
from app.core.exceptions import ToolPermissionError
from app.core.request_scope import request_session
from app.retrieval.private import PrivateKnowledgeRetriever
from app.services.container import AppContainer

router = APIRouter(prefix="/knowledge", tags=["private knowledge"])


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["bm25", "dense", "hybrid"] = "hybrid"


async def private_access(
    principal: Annotated[Principal | None, Depends(get_principal)],
    container: AppContainer = Depends(get_container),
):
    if principal is None or not isinstance(container.retriever, PrivateKnowledgeRetriever):
        raise ToolPermissionError("private knowledge is disabled or identity is unverified")
    await container.chat_service._enforce_rate_limit(principal.subject)
    return principal, container


Access = Annotated[tuple, Depends(private_access)]
DocumentID = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")]


@router.post("/documents/{document_id}")
async def create(document_id: DocumentID, payload: DocumentInput, access: Access):
    return await put(document_id, payload, access, create=True)


@router.put("/documents/{document_id}")
async def update(document_id: DocumentID, payload: DocumentInput, access: Access):
    return await put(document_id, payload, access, create=False)


async def put(document_id, payload, access, *, create):
    principal, container = access
    async with request_session(container.session_factory) as db:
        result = await container.retriever.put(
            db, principal.subject, document_id, payload.title, payload.content, create=create
        )
        if result is None:
            raise HTTPException(404, "document not found")
        await db.commit()
        return result


@router.delete("/documents/{document_id}")
async def delete(document_id: DocumentID, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        if not await container.retriever.delete(db, principal.subject, document_id):
            raise HTTPException(404, "document not found")
        await db.commit()
        return {"deleted": True}


@router.post("/reindex")
async def reindex(access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        result = await container.retriever.reindex(db, principal.subject)
        await db.commit()
        return result


@router.post("/search")
async def search(payload: SearchInput, access: Access):
    principal, container = access
    async with request_session(container.session_factory) as db:
        db.info["knowledge_subject"] = principal.subject
        chunks = await container.retriever.retrieve(
            payload.query, top_k=payload.top_k, mode=payload.mode
        )
        ranked = await container.chat_service._reranker.rerank(
            payload.query, chunks, top_n=payload.top_k
        )
        await db.commit()
        return {
            "chunks": [c.model_dump(mode="json") for c in ranked],
            "citations": [
                {"document_id": c.document_id, "chunk_id": c.chunk_id, "title": c.title}
                for c in ranked
            ],
        }
