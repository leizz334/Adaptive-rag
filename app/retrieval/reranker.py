"""Document reranking over fused retrieval results."""

from __future__ import annotations

from app.core.exceptions import RetrievalError
from app.observability.tracing import traced
from app.providers.base import RerankProvider
from app.providers.reranker import CrossEncoderRerankProvider
from app.schemas.retrieval import RetrievedChunk


class DocumentReranker:
    def __init__(self, provider: RerankProvider) -> None:
        self._provider = provider

    @traced("retrieval.rerank", "retriever")
    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        *,
        top_n: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        documents = [chunk.content for chunk in chunks]
        ranked = await self._provider.rerank(query, documents, top_n=min(top_n, len(chunks)))
        results: list[RetrievedChunk] = []
        for new_rank, (original_index, score) in enumerate(ranked, start=1):
            chunk = chunks[original_index].model_copy(deep=True)
            chunk.score = score
            chunk.rank = new_rank
            chunk.source = "rerank"
            results.append(chunk)
        return results

    @traced("retrieval.rerank.global", "retriever")
    async def rerank_global(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not isinstance(self._provider, CrossEncoderRerankProvider):
            raise RetrievalError("cross_encoder_unavailable")
        ranked = await self._provider.rerank_cross_encoder(
            query, [chunk.content for chunk in chunks]
        )
        return [
            chunks[index].model_copy(
                update={
                    "score": score,
                    "rank": rank,
                    "retrieval_score": chunks[index].score,
                }
            )
            for rank, (index, score) in enumerate(ranked, start=1)
        ]
