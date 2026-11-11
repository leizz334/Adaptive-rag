"""No DeepSeek calls: fixed real-model retrieval benchmark on frozen labels."""

import asyncio
import json
import resource
import time

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)

from .common import ARM, HERE
from .meter import write
from .retrieval import build, chunks


async def main():
    path, cfg = live_config()
    command(path, "ps")
    target = HERE / "evidence/d1_ir.json"
    if target.exists():
        raise RuntimeError(
            "preserve completed IR result;use separately authorized new immutable run"
        )
    started = time.perf_counter()
    retriever, reranker, store, modelmetrics = await build(cfg, real=True)
    records = []
    try:
        labels = json.loads((HERE / "retrieval_queries.json").read_text())["queries"]
        for q in labels:
            for arm in ["BM25", "DENSE", "HYBRID", "RERANK"]:
                token = ARM.set(arm)
                cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime
                clock = time.perf_counter()
                try:
                    hits = await retriever.retrieve(q["query"], top_k=len(chunks()))
                    if arm == "RERANK":
                        hits = await reranker.rerank(q["query"], hits, top_n=len(hits))
                    ids = [c.chunk_id for c in hits]
                    gold = set(q["relevant_ids"])
                    first = next((i + 1 for i, v in enumerate(ids) if v in gold), None)
                    records.append(
                        dict(
                            query=q["id"],
                            split=q["split"],
                            arm=arm,
                            ranking=ids,
                            relevant_ids=q["relevant_ids"],
                            recall1=len(gold & set(ids[:1])) / len(gold),
                            recall3=len(gold & set(ids[:3])) / len(gold),
                            reciprocal_rank=1 / first if first else 0,
                            latency_ms=(time.perf_counter() - clock) * 1000,
                            cpu_user_s=resource.getrusage(resource.RUSAGE_SELF).ru_utime - cpu,
                            maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        )
                    )
                    print(q["id"], arm, ids[:3], flush=True)
                finally:
                    ARM.reset(token)
        write(
            target,
            dict(
                real_models=True,
                paid_requests=0,
                model_metrics=modelmetrics,
                full_corpus_size=len(chunks()),
                model_download=json.loads((HERE / "evidence/model_download.json").read_text()),
                total_benchmark_ms=(time.perf_counter() - started) * 1000,
                records=records,
                label_provenance="separate AI author before retrieval outcomes,not human/blind",
                cache="disabled",
                mrr_scope="full frozen corpus8",
            ),
        )
    finally:
        if store._client:
            store._client.close()


if __name__ == "__main__":
    asyncio.run(main())
