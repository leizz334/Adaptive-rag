"""Re-run the original RAG evaluator with the public DeepSeek billing guard."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
from dotenv import dotenv_values
from pydantic import SecretStr

from app.config.settings import Settings
from eval import rerank_ablation as original
from eval.rag_refresh.ranking import WEIGHT_HASHES, file_digest
from eval.release.shared.budget import HOST, MODEL, REQUEST_SCOPE, Ledger, MeteredTransport

DEFAULT_CAP = Decimal("0.60")
DEFAULT_REQUESTS = 420
BASE_URL = f"https://{HOST}"


def read_key(env_file: Path | None) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key and env_file is not None:
        key = dotenv_values(env_file).get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DeepSeek API credential is required")
    return key


def preflight(key: str) -> Decimal:
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
        trust_env=False,
    ) as client:
        models = client.get("/models")
        balance = client.get("/user/balance")
    print(json.dumps({"models_http": models.status_code, "balance_http": balance.status_code}))
    if models.status_code != 200 or balance.status_code != 200:
        raise SystemExit("Could not authenticate and verify current DeepSeek budget")
    if MODEL not in {item["id"] for item in models.json()["data"]}:
        raise SystemExit(f"{MODEL} is unavailable")
    body = balance.json()
    funds = next(
        (
            Decimal(x["total_balance"])
            for x in body.get("balance_infos", [])
            if x["currency"] == "CNY"
        ),
        Decimal(0),
    )
    if not body["is_available"] or funds <= 0:
        raise SystemExit("Verified DeepSeek CNY budget unavailable")
    print(json.dumps({"model": MODEL, "available_cny": str(funds)}))
    return funds


async def run(
    settings: Settings,
    root: Path,
    ledger: Ledger,
    settings_to_run: list[str],
) -> None:
    gold = original.load_jsonl(original.RAG_PATH)
    queries = {row["query"]: row["id"] for row in gold}
    if len(queries) != len(gold):
        raise SystemExit("The frozen set must have unique queries for per-case accounting")

    class RecordedClient(original.NonThinkingClient):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs, transport=MeteredTransport(ledger), trust_env=False)

    retrieve_original = original.retrieval_node

    for setting in settings_to_run:

        async def retrieve(state, *, setting=setting, **kwargs):
            case_id = queries[state["user_query"]]
            REQUEST_SCOPE.set({"job": f"{setting}:{case_id}", "setting": setting, "case": case_id})
            return await retrieve_original(state, **kwargs)

        options = argparse.Namespace(
            groups=["A"],
            output=root / setting,
            concurrency=1,
            limit=None,
            force_two_hops=setting == "forced",
            non_thinking=True,
        )
        with (
            patch.object(original, "get_settings", return_value=settings),
            patch.object(original, "NonThinkingClient", RecordedClient),
            patch.object(original, "retrieval_node", retrieve),
        ):
            await original.run(options)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Read only DEEPSEEK_API_KEY from this file")
    parser.add_argument("--check-budget", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--embedding", type=Path)
    parser.add_argument("--reranker", type=Path)
    parser.add_argument("--embedding-device", default="cpu")
    parser.add_argument("--reranker-device", default="cpu")
    parser.add_argument("--cap-cny", type=Decimal, default=DEFAULT_CAP)
    parser.add_argument("--max-requests", type=int, default=DEFAULT_REQUESTS)
    parser.add_argument(
        "--settings", nargs="+", choices=["natural", "forced"], default=["natural", "forced"]
    )
    args = parser.parse_args()
    if not args.check_budget and not all((args.output, args.embedding, args.reranker)):
        parser.error("--output, --embedding and --reranker are required for a run")
    if not 0 < args.cap_cny <= DEFAULT_CAP or not 1 <= args.max_requests <= DEFAULT_REQUESTS:
        parser.error("the published replay is bounded by ¥0.60 and 420 requests")

    key = read_key(args.env_file)
    funds = preflight(key)
    if args.check_budget:
        return
    if funds < args.cap_cny:
        raise SystemExit("Current CNY balance is below requested replay cap")
    for name, path in (("embedding", args.embedding), ("reranker", args.reranker)):
        if file_digest(path / "model.safetensors") != WEIGHT_HASHES[name]:
            raise SystemExit(f"Unexpected {name} weights")

    import torch

    torch.set_num_threads(2)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        app_env="development",
        knowledge_dir="knowledge",
        deepseek_api_key=SecretStr(key),
        deepseek_base_url=BASE_URL,
        deepseek_model=MODEL,
        llm_max_retries=1,
        llm_timeout_seconds=30,
        llm_judge_max_tokens=512,
        embedding_api_key=SecretStr(""),
        embedding_base_url="",
        embedding_dim=512,
        local_embedding_enabled=True,
        local_embedding_model=str(args.embedding),
        local_embedding_device=args.embedding_device,
        cross_encoder_enabled=True,
        cross_encoder_model=str(args.reranker),
        cross_encoder_device=args.reranker_device,
        cross_encoder_max_length=512,
        retrieval_top_k_simple=3,
        retrieval_top_k_complex=8,
        rerank_top_n=5,
        rrf_k=60,
        max_retrieval_hops=3,
        unstructured_enabled=True,
        unstructured_strategy="auto",
    )
    args.output.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(
        args.output / "requests.sqlite3", cap_cny=args.cap_cny, max_requests=args.max_requests
    )
    try:
        asyncio.run(run(settings, args.output, ledger, args.settings))
    finally:
        dump = json.dumps(
            {"totals": ledger.totals(), "requests": ledger.requests()}, ensure_ascii=False
        )
        (args.output / "requests.json").write_text(dump + "\n", encoding="utf-8")
        print(json.dumps(ledger.totals()))


if __name__ == "__main__":
    main()
