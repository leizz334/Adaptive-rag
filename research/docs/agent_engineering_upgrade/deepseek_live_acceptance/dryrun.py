"""Estimate the unchanged greeting graph's prompt reservations with MockTransport."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import httpx

from app.agents.nodes.generate import generate_node
from app.agents.nodes.intent import IntentClassifier
from app.config.settings import Settings
from app.core.enums import RetrievalStrategy
from app.providers.deepseek import DeepSeekProvider
from app.providers.paid_budget import BudgetLimits, _request_reservation


async def main():
    requests = []
    limits = BudgetLimits(
        6, 10000, Decimal("0.05"), Decimal("0.30"), Decimal("1.20"), "deepseek-flash"
    )

    async def response(request):
        tokens, cost = _request_reservation(request.content, limits)
        body = json.loads(request.content)
        requests.append(
            {
                "bytes": len(request.content),
                "max_output": body["max_tokens"],
                "reserved_tokens": tokens,
                "reserved_usd": str(cost),
            }
        )
        value = (
            {
                "label": "greeting",
                "confidence": 1,
                "rationale": "mock forecast",
                "prompt_version": "mock",
            }
            if len(requests) == 1
            else {"answer": "仅作Mock预算预测", "citation_chunk_ids": [], "refused": False}
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )

    settings = Settings(
        _env_file=None,
        deepseek_model="deepseek-flash",
        deepseek_api_key="synthetic-only",
        deepseek_thinking_mode="disabled",
    )
    async with httpx.AsyncClient(
        base_url="https://api.deepseek.com", transport=httpx.MockTransport(response)
    ) as client:
        provider = DeepSeekProvider(settings, client=client)
        intent = await IntentClassifier(provider).classify("你好")
        await generate_node(
            {"user_query": "你好", "intent": intent, "strategy": RetrievalStrategy.DIRECT}, provider
        )
    result = {
        "mode": "MOCK_PROMPT_FORECAST_NOT_LIVE",
        "requests": requests,
        "reserved_tokens_sum": sum(row["reserved_tokens"] for row in requests),
        "note": "Actual authenticated graph can add Memory context; forecasts do not consume real ledger",
    }
    with (
        Path.cwd()
        / "research/docs/agent_engineering_upgrade/deepseek_live_acceptance/evidence/D2-greeting-forecast.json"
    ).open("x") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


asyncio.run(main())
