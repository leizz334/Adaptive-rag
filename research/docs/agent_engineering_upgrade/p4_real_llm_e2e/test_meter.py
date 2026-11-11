import json

import httpx
import pytest

from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import (
    Ledger,
    MeteredTransport,
    SafetyStop,
)


def payload():
    return dict(
        model="deepseek-flash",
        messages=[dict(role="user", content="synthetic")],
        max_tokens=16,
        temperature=0,
        thinking=dict(type="disabled"),
    )


def response():
    return dict(
        model="deepseek-flash",
        choices=[dict(message=dict(content='{"ok":true}'), finish_reason="stop")],
        usage=dict(prompt_tokens=8, completion_tokens=4, total_tokens=12),
    )


async def test_write_ahead_and_usage_and_no_header_export(tmp_path):
    ledger = Ledger(tmp_path)

    def upstream(request):
        assert json.loads(ledger.path.read_text())[0]["status"] == "PENDING"
        return httpx.Response(200, json=response())

    async with httpx.AsyncClient(
        transport=MeteredTransport(ledger, httpx.MockTransport(upstream))
    ) as client:
        await client.post(
            "https://api.deepseek.com/chat/completions",
            json=payload(),
            headers={"authorization": "Bearer PRIVATE_CANARY"},
        )
    assert ledger.totals()["accounted_tokens"] == 12
    assert "PRIVATE_CANARY" not in ledger.path.read_text()
    assert Ledger(tmp_path).rows[0]["status"] == "RESPONSE"


async def test_pending_transport_never_retries_or_resumes(tmp_path):
    ledger = Ledger(tmp_path)

    def upstream(request):
        raise httpx.ReadTimeout("uncertain")

    async with httpx.AsyncClient(
        transport=MeteredTransport(ledger, httpx.MockTransport(upstream))
    ) as client:
        with pytest.raises(SafetyStop):
            await client.post("https://api.deepseek.com/chat/completions", json=payload())
        with pytest.raises(SafetyStop):
            await client.post("https://api.deepseek.com/chat/completions", json=payload())
    assert len(ledger.rows) == 1 and ledger.rows[0]["status"] == "PENDING"
    with pytest.raises(SafetyStop):
        Ledger(tmp_path).admit(10, 10)


@pytest.mark.parametrize("limits", [dict(requests=0), dict(tokens=1), dict(usd=0)])
async def test_each_cap_stops_before_network(tmp_path, limits):
    ledger = Ledger(tmp_path, limits=limits)

    def upstream(request):
        pytest.fail("network must not be called")

    async with httpx.AsyncClient(
        transport=MeteredTransport(ledger, httpx.MockTransport(upstream))
    ) as client:
        with pytest.raises(SafetyStop):
            await client.post("https://api.deepseek.com/chat/completions", json=payload())
    assert not ledger.rows


async def test_unknown_usage_and_wrong_host_fail_closed(tmp_path):
    ledger = Ledger(tmp_path)
    async with httpx.AsyncClient(
        transport=MeteredTransport(
            ledger, httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": []}))
        )
    ) as client:
        with pytest.raises(SafetyStop):
            await client.post("https://untrusted.invalid/chat/completions", json=payload())
        assert not ledger.rows
        with pytest.raises(SafetyStop):
            await client.post("https://api.deepseek.com/chat/completions", json=payload())
    assert len(ledger.rows) == 1
    with pytest.raises(SafetyStop):
        Ledger(tmp_path).admit(1, 1)


def test_limits_cannot_expand_or_reprice_unknown_ledger(tmp_path):
    with pytest.raises(ValueError):
        Ledger(tmp_path, limits=dict(requests=81))


def test_checkpoint_syncs_parent_directory(tmp_path, monkeypatch):
    import os
    import stat

    from research.docs.agent_engineering_upgrade.p4_real_llm_e2e import meter

    real_sync = os.fsync
    synced_directory = []

    def sync(fd):
        synced_directory.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        return real_sync(fd)

    monkeypatch.setattr(os, "fsync", sync)
    meter.write(tmp_path / "reservation.json", {"status": "PENDING"})
    assert any(synced_directory)
