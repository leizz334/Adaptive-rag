"""No-network validation of the experiment-only real-provider adapter."""

import json

import httpx
import pytest

from app.config.settings import Settings
from app.core.exceptions import LLMProviderError
from research.docs.agent_engineering_upgrade.real_llm_baseline.evaluate_real import (
    Ledger,
    MeteredDeepSeek,
    summarize,
)


def setup(tmp_path, **limits):
    config = {"max_http_attempts": 2, "max_accounted_tokens": 10000, **limits}
    (tmp_path / "requests.json").write_text("[]", encoding="utf-8")
    return Ledger(tmp_path, config)


@pytest.mark.asyncio
async def test_actual_usage_model_temperature_and_base_path(tmp_path):
    ledger = setup(tmp_path)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "actual",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    provider = MeteredDeepSeek(
        Settings(
            _env_file=None,
            deepseek_api_key="SYNTHETIC_ONLY",
            deepseek_base_url="https://offline.invalid/v1",
            deepseek_model="requested",
            llm_max_retries=1,
        ),
        ledger,
        "case",
        transport=httpx.MockTransport(handler),
    )
    try:
        await provider.generate(
            [{"role": "user", "content": "read-only"}], temperature=0.2, max_tokens=20
        )
    finally:
        await provider.aclose()
    assert seen[0]["temperature"] == 0.0 and seen[0]["max_tokens"] == 20
    assert ledger.rows[0]["model_reported"] == "actual"
    assert ledger.accounted_tokens == 12
    assert "SYNTHETIC_ONLY" not in (tmp_path / "requests.json").read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="invalid JSON"),
        httpx.Response(401, json={"error": "unauthorized"}),
        httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10001, "completion_tokens": 2, "total_tokens": 10003},
            },
        ),
    ],
)
async def test_upstream_failure_stops_without_retry_or_fake_usage(tmp_path, response):
    ledger = setup(tmp_path)
    calls = []

    def handler(request):
        calls.append(request)
        return response

    provider = MeteredDeepSeek(
        Settings(
            _env_file=None,
            deepseek_api_key="SYNTHETIC_ONLY",
            deepseek_base_url="https://offline.invalid",
            llm_max_retries=1,
        ),
        ledger,
        "case",
        transport=httpx.MockTransport(handler),
    )
    try:
        for _ in range(2):
            with pytest.raises(LLMProviderError):
                await provider.generate([{"role": "user", "content": "read-only"}])
    finally:
        await provider.aclose()
    assert len(calls) == 1 and ledger.stop_reason
    assert ledger.rows[0]["failure"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limits", [{"max_http_attempts": 0}, {"max_accounted_tokens": 1}])
async def test_budget_guard_prevents_transport(tmp_path, limits):
    ledger = setup(tmp_path, **limits)
    calls = []
    provider = MeteredDeepSeek(
        Settings(
            _env_file=None,
            deepseek_api_key="SYNTHETIC_ONLY",
            deepseek_base_url="https://offline.invalid",
            llm_max_retries=1,
        ),
        ledger,
        "case",
        transport=httpx.MockTransport(lambda request: calls.append(request)),
    )
    try:
        with pytest.raises(LLMProviderError):
            await provider.generate([{"role": "user", "content": "read-only"}])
    finally:
        await provider.aclose()
    assert calls == [] and ledger.rows == []


def test_existing_probe_usage_counts_against_global_budget(tmp_path):
    ledger = setup(tmp_path)
    ledger.rows.append(
        {
            "usage": {"prompt_tokens": 46, "completion_tokens": 15, "total_tokens": 61},
            "reserved_tokens": 1238,
        }
    )
    assert ledger.accounted_tokens == 61


def test_report_does_not_score_upstream_error_as_model_failure(tmp_path):
    (tmp_path / "experiment_config.json").write_text(
        json.dumps({"selected_case_ids": ["reference"], "reference_case_ids": ["reference"]}),
        encoding="utf-8",
    )
    (tmp_path / "requests.json").write_text("[]", encoding="utf-8")
    (tmp_path / "results.json").write_text(
        json.dumps(
            {
                "status": "PARTIAL",
                "results": [
                    {
                        "case_id": "reference",
                        "status": "ERROR",
                        "metrics": {},
                        "evidence": {},
                        "reasons": ["infrastructure_error"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = summarize(tmp_path)
    assert result["attempted_cases"] == 1 and result["valid_cases"] == 0
    assert result["task_success_rate"] is None
    assert result["reference_resolution"] is None
    assert result["safety_violations"] is None


def test_rejected_usage_types_retain_reservation_and_report_unknown(tmp_path):
    ledger = setup(tmp_path)
    ledger.rows.append({"usage": {"total_tokens": "13"}, "reserved_tokens": 1238})
    ledger.save()
    assert ledger.accounted_tokens == 1238
