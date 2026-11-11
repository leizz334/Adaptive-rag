"""Fail-closed private retrieval with SQL authority and no shared-corpus fallback."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.exceptions import InvalidRequestError, RetrievalError, ToolPermissionError
from app.core.request_scope import get_db_session
from app.repositories.models import PrivateKnowledgeDocumentRow, PrivateKnowledgeTenantRow
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.vector import QdrantVectorStore, VectorRetriever, stable_point_id
from app.schemas.retrieval import RetrievedChunk


def document_chunks(row) -> list[RetrievedChunk]:
    result = []
    for index, start in enumerate(range(0, len(row.content), 1000)):
        identifier = hashlib.sha256(
            f"{row.subject}\0{row.document_id}\0{row.revision}\0{index}".encode()
        ).hexdigest()
        result.append(
            RetrievedChunk(
                chunk_id=identifier,
                document_id=row.document_id,
                title=row.title,
                content=row.content[start : start + 1000],
                score=0,
                chunk_index=index,
                policy_version=row.revision,
                metadata={"tenant_subject": row.subject, "revision": row.revision},
            )
        )
    return result


class PrivateVectorStore(QdrantVectorStore):
    def write(self, chunks, embeddings):
        from qdrant_client.models import PointStruct

        client = self._ensure_client()
        client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=stable_point_id(c.chunk_id),
                    vector=v,
                    payload={
                        "tenant_subject": c.metadata["tenant_subject"],
                        "document_id": c.document_id,
                        "revision": c.policy_version,
                        "chunk_id": c.chunk_id,
                    },
                )
                for c, v in zip(chunks, embeddings, strict=True)
            ],
            wait=True,
        )

    def scoped_search(self, subject, ids, vector, top_k):
        from qdrant_client import models

        if not ids:
            return []
        hits = self._ensure_client().search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_subject", match=models.MatchValue(value=subject)
                    ),
                    models.FieldCondition(key="chunk_id", match=models.MatchAny(any=list(ids))),
                ]
            ),
            with_payload=True,
        )
        return [(h.payload.get("chunk_id"), h.score) for h in hits if h.payload]

    def remove_document(self, subject, document_id, *, revision):
        from qdrant_client import models

        self._ensure_client().delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_subject", match=models.MatchValue(value=subject)
                        ),
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=document_id)
                        ),
                        models.FieldCondition(
                            key="revision", match=models.MatchValue(value=revision)
                        ),
                    ]
                )
            ),
            wait=True,
        )

    def search(self, query_vector, *, top_k):
        raise ToolPermissionError("private vector search requires verified scope")

    def upsert(self, records):
        raise ToolPermissionError("private vector writes require owned document transaction")


class PrivateKnowledgeRetriever(HybridRetriever):
    def __init__(self, store, embedder, redis, *, rrf_k, ttl):
        super().__init__(BM25Retriever(), VectorRetriever(store, embedder), rrf_k=rrf_k)
        self.store = store
        self.embedder = embedder
        self.redis = redis
        self.ttl = ttl

    async def _lock(self, db, subject, *, write=False):
        if not subject or subject == "anonymous" or db.bind.dialect.name != "postgresql":
            raise ToolPermissionError("private knowledge requires verified PostgreSQL scope")
        await db.execute(
            insert(PrivateKnowledgeTenantRow)
            .values(subject=subject, generation=0)
            .on_conflict_do_nothing(index_elements=["subject"])
        )
        statement = select(PrivateKnowledgeTenantRow).where(
            PrivateKnowledgeTenantRow.subject == subject
        )
        row = await db.scalar(statement.with_for_update(read=not write))
        return row

    async def _corpus(self, db, subject):
        rows = (
            await db.scalars(
                select(PrivateKnowledgeDocumentRow)
                .where(PrivateKnowledgeDocumentRow.subject == subject)
                .order_by(PrivateKnowledgeDocumentRow.document_id)
            )
        ).all()
        return [chunk for row in rows for chunk in document_chunks(row)]

    async def put(self, db, subject, document_id, title, content, *, create):
        generation = await self._lock(db, subject, write=True)
        row = await db.get(PrivateKnowledgeDocumentRow, (subject, document_id))
        if create and row is not None:
            raise InvalidRequestError("document already exists")
        if not create and row is None:
            return None
        old_revision = row.revision if row is not None else None
        if row is None:
            count = len(
                (
                    await db.scalars(
                        select(PrivateKnowledgeDocumentRow.document_id).where(
                            PrivateKnowledgeDocumentRow.subject == subject
                        )
                    )
                ).all()
            )
            if count >= 100:
                raise InvalidRequestError("private document limit reached")
            row = PrivateKnowledgeDocumentRow(subject=subject, document_id=document_id)
            db.add(row)
        row.revision, row.title, row.content = uuid.uuid4().hex, title, content
        chunks = document_chunks(row)
        vectors = await self.embedder.embed([c.content for c in chunks])
        try:
            # New immutable IDs may be orphaned if SQL rolls back; SQL never authorizes them.
            await asyncio.to_thread(self.store.write, chunks, vectors)
            if old_revision is not None:
                await asyncio.to_thread(
                    self.store.remove_document, subject, document_id, revision=old_revision
                )
        except Exception as exc:
            raise RetrievalError("private index write unavailable") from exc
        generation.generation += 1
        await db.flush()
        return {"document_id": document_id, "revision": row.revision, "chunks": len(chunks)}

    async def delete(self, db, subject, document_id):
        generation = await self._lock(db, subject, write=True)
        row = await db.get(PrivateKnowledgeDocumentRow, (subject, document_id))
        if row is None:
            return False
        try:
            await asyncio.to_thread(
                self.store.remove_document, subject, document_id, revision=row.revision
            )
        except Exception as exc:
            raise RetrievalError("private index deletion unavailable") from exc
        await db.delete(row)
        generation.generation += 1
        await db.flush()
        return True

    async def reindex(self, db, subject):
        generation = await self._lock(db, subject, write=True)
        chunks = await self._corpus(db, subject)
        if chunks:
            vectors = await self.embedder.embed([c.content for c in chunks])
            try:
                await asyncio.to_thread(self.store.write, chunks, vectors)
            except Exception as exc:
                raise RetrievalError("private reindex unavailable") from exc
        generation.generation += 1
        return {"chunks": len(chunks)}

    async def retrieve(self, query, *, top_k, mode="hybrid"):
        try:
            db = get_db_session()
        except RuntimeError as exc:
            raise ToolPermissionError("private retrieval requires verified request scope") from exc
        subject = db.info.get("knowledge_subject")
        generation = await self._lock(db, subject)
        chunks = await self._corpus(db, subject)
        canonical = {c.chunk_id: c for c in chunks}
        digest = hashlib.sha256(
            f"v1\0{subject}\0{generation.generation}\0{mode}\0{top_k}\0{query}".encode()
        ).hexdigest()
        key = "private-ret:v1:" + digest
        cached = None
        if self.redis is None:
            raise RetrievalError("private cache dependency unavailable")
        try:
            raw = await self.redis.get(key)
            if raw is not None:
                payload = json.loads(raw)
                # Never trust cached text, metadata, ordering IDs or foreign documents.
                if isinstance(payload, list) and all(
                    isinstance(i, str) and i in canonical for i in payload
                ):
                    cached = [canonical[i].model_copy(deep=True) for i in payload]
        except (ValueError, TypeError):
            pass  # Corrupt cache is a miss, never returned as evidence.
        except Exception as exc:
            raise RetrievalError("private cache dependency unavailable") from exc
        if cached is not None:
            return cached[:top_k]
        if not chunks:
            return []
        lexical = BM25Retriever(chunks).search(query, top_k=top_k) if mode != "dense" else []
        dense = []
        if mode != "bm25":
            try:
                vector = (await self.embedder.embed([query]))[0]
                hits = await asyncio.to_thread(
                    self.store.scoped_search, subject, canonical, vector, top_k
                )
                for identifier, score in hits:
                    if identifier in canonical:
                        c = canonical[identifier].model_copy(deep=True)
                        c.score, c.source = float(score), "private_vector"
                        dense.append(c)
            except Exception as exc:
                raise RetrievalError("private vector dependency unavailable") from exc
        result = reciprocal_rank_fusion([lexical, dense], k=self._rrf_k)[:top_k]
        try:
            await self.redis.set(key, json.dumps([c.chunk_id for c in result]), ex=self.ttl)
        except Exception as exc:
            raise RetrievalError("private cache dependency unavailable") from exc
        return result
