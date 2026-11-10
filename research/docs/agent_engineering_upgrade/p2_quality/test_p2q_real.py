"""Offline safety tests: only HTTP transport is replaced."""

import httpx
import pytest

from research.docs.agent_engineering_upgrade.p2_quality import real as r


def payload(**updates):
    value = {
        "model": "test",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
        "max_tokens": 32,
    }
    value.update(updates)
    return value


def reply(usage=True, finish="stop"):
    value = {
        "model": "backend",
        "choices": [
            {
                "message": {"content": "{}", "reasoning_content": "DO NOT SAVE"},
                "finish_reason": finish,
            }
        ],
    }
    if usage:
        value["usage"] = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
    return value


async def post(ledger, body=None, handler=None, group="case:M0"):
    transport = r.ReplayTransport(
        ledger,
        group,
        httpx.MockTransport(handler or (lambda request: httpx.Response(200, json=reply()))),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.post(
            "https://test/chat/completions",
            json=body or payload(),
            headers={"Authorization": "Bearer SECRET"},
        )


@pytest.mark.asyncio
async def test_completed_response_replays_without_network_or_secrets(tmp_path):
    ledger = r.Ledger(tmp_path)
    first = await post(ledger)
    resumed = r.Ledger(tmp_path)
    second = await post(resumed, handler=lambda _: pytest.fail("network on replay"))
    assert first.json() == second.json()
    assert len(resumed.rows) == 1
    assert resumed.totals()["accounted_tokens"] == 12
    saved = (tmp_path / "requests.json").read_text()
    assert "DO NOT SAVE" not in saved and "SECRET" not in saved


@pytest.mark.asyncio
async def test_replay_hash_conflict_fails_closed(tmp_path):
    ledger = r.Ledger(tmp_path)
    await post(ledger)
    with pytest.raises(r.SafetyStop, match="hash"):
        await post(r.Ledger(tmp_path), payload(max_tokens=33))


@pytest.mark.asyncio
async def test_pending_request_survives_crash_and_never_repeats(tmp_path):
    def crash(_):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        await post(r.Ledger(tmp_path), handler=crash)
    with pytest.raises(r.SafetyStop, match="uncertain"):
        await post(r.Ledger(tmp_path), handler=lambda _: pytest.fail("network"))


@pytest.mark.asyncio
@pytest.mark.parametrize("limits", [{"requests": 0}, {"tokens": 10}, {"usd": 0}])
async def test_each_hard_budget_blocks_before_http(tmp_path, limits):
    with pytest.raises(r.SafetyStop, match="budget"):
        await post(r.Ledger(tmp_path, limits=limits), handler=lambda _: pytest.fail("network"))
    assert r.Ledger(tmp_path).rows == []


@pytest.mark.asyncio
async def test_unknown_usage_charges_full_utf8_reservation(tmp_path):
    ledger = r.Ledger(tmp_path)
    await post(
        ledger,
        payload(messages=[{"role": "user", "content": "你好"}]),
        handler=lambda _: httpx.Response(200, json=reply(False)),
    )
    row = ledger.rows[0]
    assert row["usage"] is None
    assert ledger.totals()["accounted_tokens"] == row["reserve_input"] + 32
    assert row["reserve_input"] == 1120  # 96 actual UTF-8 HTTP bytes + 1024 framing reserve.


@pytest.mark.asyncio
async def test_zero_usage_is_unknown_and_cannot_erase_reservation(tmp_path):
    value = reply()
    value["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    ledger = r.Ledger(tmp_path)
    await post(ledger, handler=lambda _: httpx.Response(200, json=value))
    assert ledger.totals()["accounted_tokens"] > 1000
    assert ledger.totals()["unknown_usage_requests"] == 1


@pytest.mark.asyncio
async def test_http_error_is_counted_once_and_not_retried(tmp_path):
    ledger = r.Ledger(tmp_path)
    response = await post(ledger, handler=lambda _: httpx.Response(429, text="SECRET"))
    assert response.status_code == 429
    assert ledger.totals()["http_attempts"] == 1
    assert "SECRET" not in (tmp_path / "requests.json").read_text()


@pytest.mark.asyncio
async def test_truncation_is_durable_public_completion_and_model_error(tmp_path):
    ledger = r.Ledger(tmp_path)
    await post(
        ledger,
        payload(response_format={"type": "json_object"}),
        handler=lambda _: httpx.Response(200, json=reply(finish="length")),
    )
    assert ledger.rows[0]["model_error"] == "truncated"
    assert ledger.rows[0]["response"]["choices"][0]["message"]["content"] == "{}"


@pytest.mark.asyncio
async def test_request_stage_and_only_catalog_tool_names_are_saved(tmp_path):
    from app.prompts.planner import PLANNER_SYSTEM

    ledger = r.Ledger(tmp_path)
    system = PLANNER_SYSTEM.format(
        tools="- get_order: synthetic description [read]", skill_context="fixture"
    )
    await post(ledger, payload(messages=[{"role": "system", "content": system}]))
    assert ledger.rows[0]["stage"] == "planner"
    assert ledger.rows[0]["available_tool_names"] == ["get_order"]
    assert "synthetic description" not in (tmp_path / "requests.json").read_text()


def test_forecast_and_stats_keep_task_model_and_http_failures_separate(tmp_path):
    ledger = r.Ledger(tmp_path, limits={"tokens": 100})
    with pytest.raises(r.SafetyStop, match="forecast"):
        ledger.forecast(2, 120, 0.001)
    stats = r.summarize(
        [
            {"case_id": "a", "mode": "M0", "status": "PASS", "request_errors": []},
            {"case_id": "b", "mode": "M0", "status": "FAIL", "request_errors": []},
            {"case_id": "c", "mode": "M0", "status": "FAIL", "request_errors": ["truncated"]},
            {"case_id": "d", "mode": "M0", "status": "ERROR", "request_errors": ["http_429"]},
        ],
        ledger,
    )
    assert stats["arms"]["M0"]["task_success_including_errors"] == 0.25
    assert stats["arms"]["M0"]["task_success_valid_outputs"] == 0.5
    assert stats["arms"]["M0"]["model_invalid_groups"] == 1
    assert stats["arms"]["M0"]["http_error_groups"] == 1


@pytest.mark.asyncio
async def test_full_pilot_crash_replays_prior_http_without_repaying(tmp_path, monkeypatch):
    from eval.memory_ablation import ScriptedProvider

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-key")
    env = tmp_path / "synthetic.env"
    env.write_text("DEEPSEEK_API_KEY=test-only-key\n", encoding="utf-8")
    run = tmp_path / "run"
    script = ScriptedProvider()

    async def answer(request):
        body = __import__("json").loads(request.content)
        if body["messages"][0]["content"] == "Reply exactly P2Q_OK.":
            content = "P2Q_OK"
        else:
            response = await script.generate(
                body["messages"], response_format=body.get("response_format")
            )
            content = response.content
        value = reply()
        value["choices"][0]["message"]["content"] = content
        return httpx.Response(200, json=value)

    monkeypatch.setattr(r.httpx, "AsyncHTTPTransport", lambda **_: httpx.MockTransport(answer))
    # Freeze an actually unchanged P2 provider interface, not Settings which later
    # gains required authentication. The production baseline guard is unchanged.
    monkeypatch.setattr(
        r,
        "source_files",
        lambda: {
            "app/providers/base.py": r.digest((r.ROOT / "app/providers/base.py").read_bytes())
        },
    )
    r.prepare(run, env)
    monkeypatch.setenv("MEMORY_RECENT_MESSAGES", "100")
    with pytest.raises(r.SafetyStop, match="hash"):
        r.verify(run, env)
    monkeypatch.delenv("MEMORY_RECENT_MESSAGES")
    await r.execute("probe", run, env)
    monkeypatch.setenv("TOKEN_BUDGET", "64")
    with pytest.raises(r.SafetyStop, match="hash"):
        await r.execute("pilot", run, env)
    monkeypatch.delenv("TOKEN_BUDGET")
    with pytest.raises(r.SafetyStop, match="pilot"):
        await r.execute("run", run, env)
    original_write = r.write

    def interrupt_result(path, value):
        if path.name == "results.json" and value.get("groups"):
            raise KeyboardInterrupt()
        original_write(path, value)

    monkeypatch.setattr(r, "write", interrupt_result)
    with pytest.raises(KeyboardInterrupt):
        await r.execute("pilot", run, env)
    checkpoint = r.Ledger(run).rows
    assert len(checkpoint) > 1 and all(row["status"] == "RESPONSE" for row in checkpoint)
    prior_hashes = [row["request_sha256"] for row in checkpoint]
    monkeypatch.setattr(r, "write", original_write)
    await r.execute("pilot", run, env)
    saved = r.read(run / "results.json")
    assert [(g["case_id"], g["mode"]) for g in saved["groups"]] == [
        ("order_lookup", "M0"),
        ("order_lookup", "M1"),
        ("order_lookup", "M2"),
    ]
    assert [row["request_sha256"] for row in r.Ledger(run).rows[: len(checkpoint)]] == prior_hashes
    before = len(r.Ledger(run).rows)
    await r.execute("pilot", run, env)
    assert len(r.Ledger(run).rows) == before
    with pytest.raises(r.SafetyStop, match="already"):
        await r.execute("probe", run, env)
    config = r.read(run / "experiment_config.json")
    config["frozen_files"]["app/providers/deepseek.py"] = "tampered"
    r.write(run / "experiment_config.json", config)
    with pytest.raises(r.SafetyStop, match="hash"):
        await r.execute("run", run, env)
