"""Existing real retrieval providers, explicitly selectable evaluation arms."""

import json
import os
import resource
import time

from app.config.settings import Settings
from app.providers.embeddings import BgeM3EmbeddingProvider
from app.providers.reranker import CrossEncoderRerankProvider
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.reranker import DocumentReranker
from app.retrieval.vector import QdrantVectorStore, VectorRecord, VectorRetriever
from app.schemas.retrieval import RetrievedChunk

from .common import ARM, HERE


def chunks():
    return [
        RetrievedChunk(
            chunk_id=d["id"],
            document_id=d["id"],
            title=d["title"],
            content=d["content"],
            score=1,
            policy_version="P4D-synthetic-frozen",
        )
        for d in json.loads((HERE / "corpus.json").read_text())["documents"]
    ]


def load_models():
    import torch

    torch.set_num_threads(2)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    s = Settings(
        _env_file=None,
        app_env="testing",
        local_embedding_force=True,
        cross_encoder_force=True,
        local_embedding_model=str(HERE / ".private/models/embedding"),
        cross_encoder_model=str(HERE / ".private/models/reranker"),
        local_embedding_device="cpu",
        cross_encoder_device="cpu",
        embedding_dim=512,
    )
    start = time.perf_counter()
    embed = BgeM3EmbeddingProvider(s)
    assert embed.available, "real embedding unavailable;NO HASH fallback"
    e_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    rerank = CrossEncoderRerankProvider(s)
    assert (
        rerank.available and rerank.backend == "cross-encoder"
    ), "real reranker unavailable;NO LEXICAL fallback"
    r_ms = (time.perf_counter() - start) * 1000
    metrics = dict(
        embedding_class=type(embed._model).__name__,
        reranker_class=type(rerank._model).__name__,
        embedding_dim=embed.dim,
        embedding_cold_ms=e_ms,
        reranker_cold_ms=r_ms,
        torch_version=torch.__version__,
        threads=2,
        device="cpu",
        maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
    return embed, rerank, metrics


class Retriever:
    def __init__(self, corpus, store, embed=None):
        self.lexical = BM25Retriever(corpus)
        self.vector = VectorRetriever(store, embed) if embed else None
        self.hybrid = (
            HybridRetriever(self.lexical, self.vector, rrf_k=60, cache=None) if embed else None
        )
        self.observations = []

    async def retrieve(self, query, *, top_k):
        arm = ARM.get()
        started = time.perf_counter()
        if arm in ["DENSE"]:
            assert self.vector is not None
            hits = await self.vector.search(query, top_k=top_k)
        elif arm in ["HYBRID", "RERANK"]:
            assert self.hybrid is not None
            hits = await self.hybrid.retrieve(query, top_k=top_k)
        else:
            hits = self.lexical.search(query, top_k=top_k)
        self.observations.append(
            dict(
                arm=arm,
                query=query,
                ids=[c.chunk_id for c in hits],
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        )
        return hits


class Reranker:
    def __init__(self, real=None):
        self.real = DocumentReranker(real) if real else None

    async def rerank(self, query, values, *, top_n):
        if ARM.get() == "RERANK":
            assert self.real is not None
            return await self.real.rerank(query, values, top_n=top_n)
        return values[:top_n]


async def build(cfg, real):
    corpus = chunks()
    embed = rerank = None
    metrics = {}
    if real:
        embed, rerank, metrics = load_models()
    store = QdrantVectorStore(
        cfg["qdrant_url"], cfg["collection"] + "_d_real", embed.dim if embed else 512
    )
    assert store.ping(), "real Qdrant unavailable"
    if embed:
        vectors = await embed.embed([c.content for c in corpus])
        store.upsert([VectorRecord(c, v) for c, v in zip(corpus, vectors, strict=True)])
    return Retriever(corpus, store, embed), Reranker(rerank), store, metrics
