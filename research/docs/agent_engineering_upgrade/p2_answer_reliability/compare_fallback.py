"""Explicit source-root, zero-HTTP baseline/candidate fallback reproducer."""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path


async def run():
    from app.agents.nodes.faithfulness import faithfulness_node
    from app.core.enums import RetrievalStrategy
    from app.core.exceptions import LLMTruncationError
    from app.guardrails.hallucination import FaithfulnessChecker
    from app.schemas.agent import ToolResult
    from app.schemas.retrieval import RetrievedChunk

    class Broken:
        async def generate(self, *args, **kwargs):
            raise LLMTruncationError()

    llm = Broken()
    states = [
        dict(
            user_query="查询订单ORD8080总金额和物流",
            strategy=RetrievalStrategy.AGENT,
            final_answer="原回答",
            tool_results=[
                ToolResult(
                    name="get_order",
                    success=True,
                    output=dict(order_id="ORD8080", status="paid", total_cents=15678),
                ),
                ToolResult(
                    name="track_shipment",
                    success=True,
                    output=dict(order_id="ORD8080", events=[dict(status="in_transit")]),
                ),
            ],
        ),
        dict(
            user_query="SKU-X1人为损坏能保修吗",
            strategy=RetrievalStrategy.SINGLE,
            final_answer="不能确认",
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="c",
                    document_id="d",
                    title="不相关政策",
                    content="电池与耗材的其他规则",
                    score=1,
                )
            ],
        ),
    ]
    return [await faithfulness_node(s, FaithfulnessChecker(llm), llm) for s in states]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))
    import app

    assert Path(app.__file__).resolve().is_relative_to(args.source_root.resolve())
    value = dict(
        source_root=str(args.source_root),
        origin="MOCK_TRUNCATION_REEXECUTION_NOT_REAL_LLM",
        http_requests=0,
        source_hashes={
            str(p.relative_to(args.source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (args.source_root / "app").rglob("*.py")
        },
        results=asyncio.run(run()),
    )
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(
            value,
            out,
            ensure_ascii=False,
            indent=2,
            default=lambda obj: obj.model_dump(mode="json"),
        )
