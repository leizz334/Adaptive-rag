"""Run or verify the four-arm ranking comparison on the release Gold set."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import subprocess
import time
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from statistics import mean
from typing import Any

from app.config.settings import Settings
from app.providers.embeddings import BgeM3EmbeddingProvider
from app.providers.reranker import CrossEncoderRerankProvider
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.ingest import ingest_to_memory
from app.retrieval.reranker import DocumentReranker
from app.retrieval.vector import VectorRetriever
from app.schemas.retrieval import RetrievedChunk
from eval.metrics import percentile
from eval.rerank_ablation import ranking_metrics
from eval.runner import _doc_stem, load_jsonl

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "eval/dataset/rag_eval.jsonl"
KNOWLEDGE = ROOT / "knowledge"
HISTORICAL = ROOT / "eval/release/evidence/rag/natural/manifest.json"
ARMS = ("bm25", "vector", "hybrid", "hybrid_cross_encoder")
DEPTH = 8
LEGACY_DEPTH = 5
RRF_K = 60
THREADS = 2
WEIGHT_HASHES = {
    "embedding": "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026",
    "reranker": "ced967c45fd1902eb92716c9ceeca7c95a936770ea9db611f5a841b926e33fbd",
}


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_inputs() -> tuple[dict, list[dict]]:
    historical = json.loads(HISTORICAL.read_bytes())
    inputs = {
        "gold_sha256": file_digest(GOLD),
        "knowledge_sha256": {
            path.relative_to(KNOWLEDGE).as_posix(): file_digest(path)
            for path in sorted(KNOWLEDGE.rglob("*.md"))
        },
    }
    for key, value in inputs.items():
        if value != historical[key]:
            raise ValueError(f"Release benchmark input differs from historical {key}")
    rows = load_jsonl(GOLD)
    if [row["id"] for row in rows] != historical["case_ids"]:
        raise ValueError("Gold case IDs differ from the historical benchmark")
    return inputs, rows


def ranked_chunks(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {"id": chunk.chunk_id, "doc": _doc_stem(chunk.document_id), "score": chunk.score}
        for chunk in chunks
    ]


def metrics(gold: set[str], chunks: list[dict]) -> dict:
    docs = list(dict.fromkeys(chunk["doc"] for chunk in chunks))
    return ranking_metrics(gold, docs)


def summarize(cases: list[dict]) -> dict:
    result: dict[str, Any] = {"n": len(cases), "systems": {}}
    for arm in ARMS:
        system = {}
        for cohort, selected in (
            ("all", cases),
            ("single", [row for row in cases if len(row["gold_docs"]) == 1]),
            ("multi", [row for row in cases if len(row["gold_docs"]) > 1]),
        ):
            scores = [metrics(set(row["gold_docs"]), row["ranks"][arm]) for row in selected]
            durations = [row["latency_ms"][arm] for row in selected]
            system[cohort] = {
                "n": len(selected),
                "ranking": {key: mean(score[key] for score in scores) for key in scores[0]},
                "latency_ms": {f"p{p}": percentile(durations, p) for p in (50, 95)},
            }
        legacy = [metrics(set(row["gold_docs"]), row["legacy_ranks"][arm]) for row in cases]
        system["legacy_depth_ranking"] = {
            key: mean(score[key] for score in legacy)
            for key in ("p@1", "recall@3", "hit@1", "hit@3", "mrr")
        }
        result["systems"][arm] = system
    result["cross_encoder_vs_hybrid"] = {
        metric: {
            relation: [
                row["id"]
                for row in cases
                if (
                    metrics(set(row["gold_docs"]), row["ranks"]["hybrid_cross_encoder"])[metric]
                    - metrics(set(row["gold_docs"]), row["ranks"]["hybrid"])[metric]
                )
                * sign
                > 0
            ]
            for relation, sign in (("improved", 1), ("worsened", -1))
        }
        for metric in ("p@1", "recall@3", "ndcg@3", "mrr")
    }
    return result


def validate(cases: list[dict], gold_rows: list[dict], knowledge: dict) -> None:
    valid_docs = {Path(name).stem for name in knowledge}
    for row, gold_row in zip(cases, gold_rows, strict=True):
        if (row["id"], row["gold_docs"]) != (gold_row["id"], gold_row["relevant_doc_ids"]):
            raise ValueError("Per-case records do not match Gold IDs and document sets")
        ranks = row["ranks"]
        legacy = row["legacy_ranks"]
        if set(ranks) != set(legacy) or set(ranks) != set(ARMS):
            raise ValueError(f"{row['id']}: incorrect benchmark arms")
        for arm in ARMS:
            chunks = ranks[arm]
            if len(chunks) != DEPTH or len({chunk["id"] for chunk in chunks}) != DEPTH:
                raise ValueError(f"{row['id']}/{arm}: invalid chunk pool")
            if any(
                chunk["doc"] not in valid_docs or not math.isfinite(chunk["score"])
                for chunk in chunks
            ):
                raise ValueError(f"{row['id']}/{arm}: invalid document or score")
            if len(legacy[arm]) != LEGACY_DEPTH:
                raise ValueError(f"{row['id']}/{arm}: invalid historical depth")
        hybrid_pool = {chunk["id"]: chunk["doc"] for chunk in ranks["hybrid"]}
        rerank_pool = {chunk["id"]: chunk["doc"] for chunk in ranks["hybrid_cross_encoder"]}
        if hybrid_pool != rerank_pool:
            raise ValueError(f"{row['id']}: Cross-Encoder changed candidate membership")
        for arm in ("bm25", "vector", "hybrid_cross_encoder"):
            if legacy[arm] != ranks[arm][:LEGACY_DEPTH]:
                raise ValueError(f"{row['id']}/{arm}: incorrect historical slice")
        for depth, ranked in ((DEPTH, ranks), (LEGACY_DEPTH, legacy)):
            inputs = [
                [
                    RetrievedChunk(
                        chunk_id=chunk["id"],
                        document_id=f"{chunk['doc']}_evidence",
                        title="",
                        content="",
                        score=chunk["score"],
                    )
                    for chunk in ranked[arm]
                ]
                for arm in ("bm25", "vector")
            ]
            expected = ranked_chunks(reciprocal_rank_fusion(inputs, k=RRF_K)[:depth])
            if expected != ranked["hybrid"]:
                raise ValueError(f"{row['id']}: saved RRF differs from component rankings")
        reranked_scores = [chunk["score"] for chunk in ranks["hybrid_cross_encoder"]]
        if reranked_scores != sorted(reranked_scores, reverse=True):
            raise ValueError(f"{row['id']}: Cross-Encoder scores are out of order")


async def run(args: argparse.Namespace, inputs: dict, gold_rows: list[dict]) -> None:
    import torch

    torch.set_num_threads(THREADS)
    historical = json.loads(HISTORICAL.read_bytes())
    models = {}
    for arm, path in (("embedding", args.embedding_model), ("reranker", args.reranker_model)):
        weight_digest = file_digest(path / "model.safetensors")
        if weight_digest != WEIGHT_HASHES[arm]:
            raise ValueError(f"{arm} weights differ from the pinned historical checkpoint")
        models[arm] = {
            "checkpoint": historical[f"{arm}_checkpoint"],
            "revision": historical[f"{arm}_revision"],
            "weights_sha256": weight_digest,
        }
    settings = Settings.model_construct(
        app_env="development",
        local_embedding_enabled=True,
        local_embedding_model=str(args.embedding_model.resolve()),
        local_embedding_device="cpu",
        cross_encoder_enabled=True,
        cross_encoder_model=str(args.reranker_model.resolve()),
        cross_encoder_device="cpu",
        cross_encoder_max_length=512,
        unstructured_enabled=True,
        unstructured_strategy="auto",
    )
    embedder = BgeM3EmbeddingProvider(settings)
    if not embedder.available:
        raise RuntimeError(f"Pinned local embedding unavailable: {embedder.load_error}")
    print("Building the release policy index", flush=True)
    bm25, store, corpus = await ingest_to_memory(str(KNOWLEDGE), embedder, settings)
    vector = VectorRetriever(store, embedder)
    provider = CrossEncoderRerankProvider(settings)
    if not provider.available:
        raise RuntimeError(f"Pinned Cross-Encoder unavailable: {provider.load_error}")
    reranker = DocumentReranker(provider)
    print(f"Ranking {len(gold_rows)} queries against {len(corpus)} indexed chunks", flush=True)
    cases = []
    for row in gold_rows:
        query = row["query"]
        started = time.perf_counter()
        lexical = bm25.search(query, top_k=DEPTH)
        lexical_end = time.perf_counter()
        dense = await vector.search(query, top_k=DEPTH)
        dense_end = time.perf_counter()
        fused = reciprocal_rank_fusion([lexical, dense], k=RRF_K)[:DEPTH]
        fusion_end = time.perf_counter()
        reranked = await reranker.rerank(query, fused, top_n=DEPTH)
        rerank_end = time.perf_counter()
        cases.append(
            {
                "id": row["id"],
                "gold_docs": row["relevant_doc_ids"],
                "ranks": dict(
                    zip(ARMS, map(ranked_chunks, (lexical, dense, fused, reranked)), strict=True)
                ),
                "legacy_ranks": dict(
                    zip(
                        ARMS,
                        map(
                            ranked_chunks,
                            (
                                lexical[:LEGACY_DEPTH],
                                dense[:LEGACY_DEPTH],
                                reciprocal_rank_fusion(
                                    [lexical[:LEGACY_DEPTH], dense[:LEGACY_DEPTH]], k=RRF_K
                                )[:LEGACY_DEPTH],
                                reranked[:LEGACY_DEPTH],
                            ),
                        ),
                        strict=True,
                    )
                ),
                "latency_ms": dict(
                    zip(
                        ARMS,
                        (
                            1000 * duration
                            for duration in (
                                lexical_end - started,
                                dense_end - lexical_end,
                                fusion_end - started,
                                rerank_end - started,
                            )
                        ),
                        strict=True,
                    )
                ),
            }
        )
        if len(cases) % 10 == 0:
            print(f"Ranked {len(cases)}/{len(gold_rows)} queries", flush=True)
    validate(cases, gold_rows, inputs["knowledge_sha256"])
    corpus_digest = hashlib.sha256(
        "\n".join(f"{chunk.chunk_id}:{chunk.content}" for chunk in corpus).encode()
    ).hexdigest()
    manifest = {
        **inputs,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "kb_chunk_count": len(corpus),
        "knowledge_file_count": len(inputs["knowledge_sha256"]),
        "kb_chunk_parsers": dict(
            Counter(chunk.metadata.get("parser", "unknown") for chunk in corpus)
        ),
        "corpus_sha256": corpus_digest,
        "historical_corpus_match": corpus_digest == historical["corpus_sha256"],
        "models": models,
        "packages": {
            package: version(package)
            for package in (
                "sentence-transformers",
                "transformers",
                "torch",
                "unstructured",
                "jieba",
                "rank-bm25",
            )
        },
        "device": "cpu",
        "torch_num_threads": THREADS,
        "cross_encoder_max_length": settings.cross_encoder_max_length,
        "rrf_k": RRF_K,
        "chunk_depth": DEPTH,
        "legacy_chunk_depth": LEGACY_DEPTH,
        "ranking_unit": "first occurrence of each policy document among retained chunks",
        "timing_scope": "sequential query scoring in one process, excluding index and model loading",
        "paid_requests": 0,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in cases),
        encoding="utf-8",
    )
    (args.output / "summary.json").write_text(
        json.dumps(summarize(cases), indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embedding-model", type=Path)
    parser.add_argument("--reranker-model", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    inputs, gold_rows = checked_inputs()
    if args.verify:
        manifest = json.loads((args.output / "manifest.json").read_bytes())
        if any(manifest.get(key) != value for key, value in inputs.items()):
            raise ValueError("Saved manifest differs from the verified Gold and policies")
        cases = load_jsonl(args.output / "cases.jsonl")
        validate(cases, gold_rows, inputs["knowledge_sha256"])
        if summarize(cases) != json.loads((args.output / "summary.json").read_bytes()):
            raise ValueError("Saved summary differs from recomputed ranking metrics")
        print(f"Verified {len(cases)} cases across {len(ARMS)} retrieval arms")
        return
    if args.embedding_model is None or args.reranker_model is None:
        parser.error("a new run requires --embedding-model and --reranker-model")
    if any(
        (args.output / name).exists() for name in ("manifest.json", "cases.jsonl", "summary.json")
    ):
        parser.error("output directory already contains ranking evidence")
    asyncio.run(run(args, inputs, gold_rows))


if __name__ == "__main__":
    main()
