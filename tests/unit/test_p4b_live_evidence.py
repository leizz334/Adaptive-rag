"""Offline harness fault tests: HTTP/SQL methods are recording doubles, not E2E."""

import json
from unittest.mock import Mock

import httpx
import pytest

from research.docs.agent_engineering_upgrade.p4_dependency_integration import live_api


def run_fixture(tmp_path):
    run = live_api.LiveApi.__new__(live_api.LiveApi)
    run.directory = tmp_path
    run.cfg = {}
    run.sequence = 0
    run.processes = [dict(directory=tmp_path, url="http://127.0.0.1:1")]
    run.client = Mock()
    return run


def test_http_error_survives_snapshot_and_trace_capture_faults(tmp_path, monkeypatch):
    run = run_fixture(tmp_path)
    (tmp_path / "events.jsonl").write_text('{"partial":')
    run.client.request.side_effect = httpx.ConnectError("synthetic offline")

    async def snapshot(_):
        raise RuntimeError("synthetic database outage")

    monkeypatch.setattr(live_api, "snapshot", snapshot)
    with pytest.raises(httpx.ConnectError):
        run.request("fault", dict(message="synthetic"))
    row = json.loads((tmp_path / "request_001_fault.json").read_bytes())
    assert row["transport_error"] == "ConnectError"
    assert row["snapshot_before_error"] == "RuntimeError"
    assert row["snapshot_after_error"] == "RuntimeError"
    assert row["event_capture_errors"]


def test_successful_http_with_incomplete_evidence_is_not_pass(tmp_path, monkeypatch):
    run = run_fixture(tmp_path)
    run.client.request.return_value = httpx.Response(200, json={"answer": "synthetic"})

    async def snapshot(_):
        raise OSError("synthetic database outage")

    monkeypatch.setattr(live_api, "snapshot", snapshot)
    with pytest.raises(RuntimeError, match="incomplete request evidence"):
        run.request("partial", dict(message="synthetic"), expected=200)
    row = json.loads((tmp_path / "request_001_partial.json").read_bytes())
    assert row["status"] == 200 and row["body"]["answer"] == "synthetic"
    assert row["evidence_complete"] is False


@pytest.mark.parametrize("fault", ["noop", "duplicate_audit", "missing_idempotency"])
def test_two_http_200_cannot_replace_confirmation_state_proof(fault):
    before = dict(orders=[dict(order_id="synthetic", status="paid")], audit_logs=[])
    after = dict(
        orders=[dict(order_id="synthetic", status="cancelled")],
        audit_logs=[dict(payload="synthetic", action="cancel_order", trace_id="trace")],
        idempotency_keys=[
            dict(
                key="action",
                fingerprint="fp",
                response_json=json.dumps(dict(order_id="synthetic", status="cancelled")),
            )
        ],
    )
    if fault == "noop":
        after["orders"][0]["status"] = "paid"
    elif fault == "duplicate_audit":
        after["audit_logs"] *= 2
    else:
        after["idempotency_keys"] = []
    with pytest.raises(AssertionError):
        live_api.assert_confirmation_effects(before, after, "synthetic", "action", {"trace"})


def test_owned_process_stop_interface_is_present():
    assert callable(live_api.LiveApi.stop)


@pytest.mark.parametrize("content", [b"null", b'{"case":"\xe4'])
def test_nonobject_or_truncated_utf8_event_never_masks_http_error(tmp_path, monkeypatch, content):
    run = run_fixture(tmp_path)
    (tmp_path / "events.jsonl").write_bytes(content)
    run.client.request.side_effect = httpx.ConnectError("synthetic offline")

    async def snapshot(_):
        return {}

    monkeypatch.setattr(live_api, "snapshot", snapshot)
    with pytest.raises(httpx.ConnectError):
        run.request("corrupt", dict(message="synthetic"))
    row = json.loads((tmp_path / "request_001_corrupt.json").read_bytes())
    assert row["transport_error"] == "ConnectError" and row["event_capture_errors"]
