"""Offline safety and provenance checks; HTTP is always a MockTransport."""

import importlib
import json
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

MODULE = "research.docs.agent_engineering_upgrade.p2_agent_quality.real_pairs"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch, event_loop):
    def blocked(*args, **kwargs):
        raise AssertionError("Real sockets forbidden in R5 tooling tests")

    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    yield
    monkeypatch.undo()  # Windows asyncio's teardown creates its internal socketpair.


@pytest.fixture
def r():
    return importlib.import_module(MODULE)


def body(**updates):
    value = {
        "model": "test",
        "messages": [{"role": "user", "content": "synthetic"}],
        "temperature": 0,
        "max_tokens": 32,
    }
    return value | updates


def reply(content="{}", known=True):
    value = {
        "model": "test",
        "choices": [
            {
                "message": {"content": content, "reasoning_content": "HIDDEN_REASONING"},
                "finish_reason": "stop",
            }
        ],
    }
    if known:
        value["usage"] = {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
    return value


async def post(
    r,
    ledger,
    *,
    payload=None,
    handler=None,
    group="synthetic:R0:0",
    source="source",
    config="config",
    sequence=0,
):
    transport = r.Transport(
        ledger,
        group,
        source_sha256=source,
        config_sha256=config,
        underlying=httpx.MockTransport(handler or (lambda _: httpx.Response(200, json=reply()))),
    )
    transport.sequence = sequence
    async with httpx.AsyncClient(transport=transport) as client:
        return await client.post(
            "https://example.invalid/chat/completions",
            json=payload or body(),
            headers={"Authorization": "Bearer SECRET_TEST_ONLY"},
        )


def test_harness_exists_before_feature_work():
    assert (HERE / "real_pairs.py").is_file(), "R5 source-paired harness is missing"


def test_new_ledger_limits_and_each_budget_are_hard(r, tmp_path):
    ledger = r.Ledger(tmp_path)
    assert ledger.limits == {"requests": 420, "tokens": 420000, "usd": 3.0}
    ledger.forecast(420, 420000, 0)
    for requests, tokens, usd in [(421, 0, 0), (0, 420001, 0), (0, 0, 3.01)]:
        with pytest.raises(r.SafetyStop):
            ledger.forecast(requests, tokens, usd)
    with pytest.raises(r.SafetyStop):
        r.Ledger(tmp_path, limits={"requests": 421})


@pytest.mark.parametrize("limits", [{"requests": 0}, {"tokens": 0}, {"usd": 0}])
async def test_each_global_limit_blocks_before_http(r, tmp_path, limits):
    ledger = r.Ledger(tmp_path, limits=limits)
    with pytest.raises(r.SafetyStop, match="budget"):
        await post(r, ledger, handler=lambda _: pytest.fail("global limit reached HTTP"))
    assert ledger.rows == []


async def test_reservation_is_durable_and_response_is_whitelisted_before_return(r, tmp_path):
    ledger = r.Ledger(tmp_path)

    def handler(_):
        saved = json.loads((tmp_path / "requests.json").read_bytes())
        assert saved[-1]["status"] == "PENDING"
        assert saved[-1]["source_sha256"] == "source"
        return httpx.Response(200, json=reply())

    await post(r, ledger, handler=handler)
    saved = json.loads((tmp_path / "requests.json").read_bytes())
    assert saved[-1]["status"] == "RESPONSE"
    assert saved[-1]["latency_ms"] >= 0
    text = (tmp_path / "requests.json").read_text()
    assert "SECRET_TEST_ONLY" not in text and "HIDDEN_REASONING" not in text


async def test_completed_same_hash_replay_has_no_http(r, tmp_path):
    first = await post(r, r.Ledger(tmp_path))
    second = await post(
        r, r.Ledger(tmp_path), handler=lambda _: pytest.fail("replay dispatched HTTP")
    )
    assert first.json() == second.json()
    assert len(r.Ledger(tmp_path).rows) == 1


@pytest.mark.parametrize("change", ["request", "source", "config"])
async def test_replay_refuses_request_source_or_config_drift(r, tmp_path, change):
    await post(r, r.Ledger(tmp_path))
    kwargs = {"payload": body(max_tokens=33)} if change == "request" else {change: "changed"}
    with pytest.raises(r.SafetyStop, match="hash|fingerprint|source|config"):
        await post(
            r, r.Ledger(tmp_path), handler=lambda _: pytest.fail("drift reached HTTP"), **kwargs
        )


async def test_timeout_keeps_pending_and_latency_and_never_retries(r, tmp_path):
    def timeout(_):
        raise httpx.ReadTimeout("private body must not be saved")

    with pytest.raises(r.SafetyStop):
        await post(r, r.Ledger(tmp_path), handler=timeout)
    ledger = r.Ledger(tmp_path)
    assert len(ledger.rows) == 1
    assert ledger.rows[0]["status"] == "PENDING"
    assert ledger.rows[0]["latency_ms"] >= 0
    assert ledger.rows[0]["transport_error_type"] == "ReadTimeout"
    assert "private body" not in (tmp_path / "requests.json").read_text()
    with pytest.raises(r.SafetyStop, match="uncertain"):
        await post(r, ledger, handler=lambda _: pytest.fail("pending attempt repeated"))


async def test_stream_read_timeout_also_persists_failure_latency(r, tmp_path):
    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise httpx.ReadTimeout("body read failed")
            yield b""  # Make this an async generator without yielding response bytes.

    with pytest.raises(r.SafetyStop):
        await post(
            r, r.Ledger(tmp_path), handler=lambda _: httpx.Response(200, stream=BrokenStream())
        )
    row = r.Ledger(tmp_path).rows[0]
    assert row["status"] == "PENDING" and row["latency_ms"] >= 0


async def test_provider_forces_zero_temperature_single_attempt_and_common_cap(
    r, tmp_path, monkeypatch
):
    def answer(request):
        payload = json.loads(request.content)
        assert payload["temperature"] == 0 and payload["max_tokens"] == 1024
        return httpx.Response(200, json=reply())

    monkeypatch.setattr(r.httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(answer))
    settings = r.old.Settings(
        _env_file=None, deepseek_api_key="SECRET_TEST_ONLY", llm_max_retries=3
    )
    provider = r.Provider(
        settings,
        r.Ledger(tmp_path),
        "synthetic:R0:0",
        source_sha256="source",
        config_sha256="config",
    )
    try:
        assert provider._settings.llm_max_retries == 1
        await provider.generate(
            [{"role": "user", "content": "synthetic"}], temperature=0.8, max_tokens=4096
        )
    finally:
        await provider.aclose()


async def test_unknown_usage_charges_reservation_at_frozen_prices(r, tmp_path):
    ledger = r.Ledger(tmp_path, pricing={"input": 2.0, "output": 4.0})
    await post(r, ledger, handler=lambda _: httpx.Response(200, json=reply(known=False)))
    row = ledger.rows[0]
    totals = ledger.totals()
    assert totals["accounted_tokens"] == row["reserve_input"] + row["reserve_output"]
    assert totals["estimated_usd"] == pytest.approx(
        (row["reserve_input"] * 2 + row["reserve_output"] * 4) / 1000000
    )
    assert totals["unknown_usage_requests"] == 1


async def test_group_request_cap_blocks_before_twenty_fifth_dispatch(r, tmp_path):
    ledger = r.Ledger(tmp_path)
    await post(r, ledger)
    row = ledger.rows[0]
    ledger.rows = [dict(row, sequence=i) for i in range(24)]
    ledger.save()
    with pytest.raises(r.SafetyStop, match="group|budget"):
        await post(r, ledger, sequence=24, handler=lambda _: pytest.fail("25th HTTP"))
    assert len(ledger.rows) == 24


def test_source_configuration_drift_fails_closed(r):
    frozen = {"head": "a", "files": {"app/a.py": "a"}, "provider_settings_sha256": "x"}
    r.verify_fingerprint(frozen, dict(frozen))
    with pytest.raises(r.SafetyStop, match="fingerprint|source|config"):
        r.verify_fingerprint(frozen, frozen | {"head": "b"})


def test_deterministic_id_only_selection_is_order_independent(r):
    ids = [f"synthetic-{i}" for i in range(12)]
    selected = r.select_blind(ids)
    assert selected == r.select_blind(list(reversed(ids)))
    assert len(selected) == 6 and len(set(selected)) == 6
    import hashlib

    assert (
        selected
        == sorted(
            ids, key=lambda case: hashlib.sha256(("P2R-20261105" + case).encode()).hexdigest()
        )[:6]
    )


def test_lexical_and_schema_errors_are_separate_diagnostics(r):
    def row(content):
        return {
            "stage": "planner",
            "expects_json": True,
            "response": reply(content),
            "model_error": None,
        }

    assert r.analyze_response(row("```json\n{}\n```"))["lexical_error"] == "invalid_json_object"
    malformed = r.analyze_response(row('{"steps": "not-a-list"}'))
    assert malformed["lexical_error"] is None and malformed["schema_error"]
    valid = r.analyze_response(row('{"steps": []}'))
    assert valid == {"lexical_error": None, "schema_error": None}


def test_real_provenance_overrides_default_without_losing_raw_driver(r):
    raw = {"case_id": "synthetic", "status": "PASS", "model_evaluation": "NOT_RUN"}
    group = r.attach_provenance(
        raw,
        [{"status": "RESPONSE", "model_error": None, "http_status": 200}],
        variant="R0",
        rep=0,
        live_attempts=1,
    )
    assert group["model_evaluation"] == "REAL_PROVIDER"
    assert group["raw_driver_result"]["model_evaluation"] == "NOT_RUN"
    assert group["evidence_origin"] == "REAL_PROVIDER_COMPLETIONS"


def test_worker_binds_source_before_application_imports(r, tmp_path):
    # A separate directory defeats accidental dependence on the harness package root.
    import shutil

    for name in ("app", "eval"):
        shutil.copytree(
            ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    code = "import runpy,socket,sys; socket.socket.connect=lambda *a:(_ for _ in ()).throw(AssertionError('socket')); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(HERE / "real_pairs.py"),
            "_imports",
            "--source-root",
            str(tmp_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    assert Path(actual["app_settings"]).resolve().is_relative_to(tmp_path)
    assert Path(actual["eval_multiturn"]).resolve().is_relative_to(tmp_path)


def test_old_pending_ledger_is_never_loaded(r, tmp_path):
    prior = tmp_path / "old"
    prior.mkdir()
    (prior / "requests.json").write_text('[{"status":"PENDING"}]')
    fresh = tmp_path / "new"
    assert r.Ledger(fresh).rows == []


def test_dirty_source_snapshot_is_rejected(r, monkeypatch):
    monkeypatch.setattr(r.subprocess, "check_output", lambda *a, **k: "head")
    monkeypatch.setattr(
        r.subprocess, "run", lambda *a, **k: type("Result", (), {"returncode": 1})()
    )
    with pytest.raises(r.SafetyStop, match="clean|snapshot|source"):
        r.clean_source_head(r.SOURCE_ROOT)


async def test_mocked_prepare_probe_group_and_interrupted_result_replay(r, tmp_path, monkeypatch):
    from argparse import Namespace

    from eval.memory_ablation import ScriptedProvider

    env = tmp_path / "synthetic.env"
    env.write_text("DEEPSEEK_API_KEY=SECRET_TEST_ONLY\n", encoding="utf-8")
    # Full-suite tests/conftest intentionally overrides developer credentials;
    # this HTTP-mocked test must explicitly scope its own synthetic credential.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_TEST_ONLY")
    dev = tmp_path / "dev.json"
    blind = tmp_path / "blind.json"

    def case(identifier, message):
        return {
            "id": identifier,
            "family": "synthetic",
            "user_goal": "synthetic fixture",
            "turns": [{"message": message}],
        }

    dev.write_text(
        json.dumps(
            {
                "schema_version": "agent-scenarios-v2.1",
                "scenarios": [case(i, "查 ORD10003 的订单状态") for i in r.DEV_IDS],
            }
        ),
        encoding="utf-8",
    )
    blind.write_text(
        json.dumps(
            {
                "schema_version": "agent-scenarios-v2.1",
                "scenarios": [case(f"synthetic-blind-{i}", "你好") for i in range(33)],
            }
        ),
        encoding="utf-8",
    )
    common = dict(
        files={},
        source_sha256="synthetic-source",
        imports={},
        provider_settings_sha256="synthetic-settings",
        ambient_settings_sha256="synthetic-ambient",
        endpoint="https://example.invalid",
        model="test",
        key_recognized=True,
        caps={},
        prompts={},
    )
    snapshots = {"R0": dict(common, head=r.BASE), "R1": dict(common, head="candidate")}
    pending = iter(snapshots.values())
    monkeypatch.setattr(r, "worker_snapshot", lambda *a: next(pending))
    monkeypatch.setattr(r, "fingerprint", lambda *a: snapshots["R0"])
    run = tmp_path / "new-run"
    run.mkdir()
    args = Namespace(
        run_dir=run,
        r0_root=r.SOURCE_ROOT,
        r1_root=r.SOURCE_ROOT,
        candidate_commit="candidate",
        env_file=env,
        dev_dataset=dev,
        blind_dataset=blind,
        input_price=0.30,
        output_price=1.20,
        pricing_url="https://example.invalid/pricing",
        pricing_verified_date="2026-11-05",
        project_root=r.HARNESS_ROOT,
        variant="R0",
        rep=0,
        case_id="dv01",
        command="probe",
    )
    with r.exclusive(run):
        assert r.prepare(args)["status"] == "PREPARED"
    script = ScriptedProvider()

    async def answer(request):
        payload = json.loads(request.content)
        if payload["messages"] == [{"role": "user", "content": "Reply exactly P2R_OK."}]:
            content = "P2R_OK"
        else:
            content = (
                await script.generate(
                    payload["messages"], response_format=payload.get("response_format")
                )
            ).content
        return httpx.Response(200, json=reply(content))

    monkeypatch.setattr(r.httpx, "AsyncHTTPTransport", lambda **kw: httpx.MockTransport(answer))
    assert (await r.execute(args))["status"] == "PROBE_COMPLETE"
    args.command = "run-group"
    write = r.write

    def crash_after_http(path, value):
        if path.name == "results.json" and value.get("groups"):
            raise KeyboardInterrupt()
        write(path, value)

    monkeypatch.setattr(r, "write", crash_after_http)
    with pytest.raises(KeyboardInterrupt):
        await r.execute(args)
    before = r.Ledger(run).rows
    assert len(before) > 1 and all(row["status"] == "RESPONSE" for row in before)
    monkeypatch.setattr(r, "write", write)
    await r.execute(args)
    assert len(r.Ledger(run).rows) == len(before)
    group = r.read(run / "results.json")["groups"][0]
    assert (
        group["new_http_attempts"] == 0
        and group["raw_driver_result"]["model_evaluation"] == "NOT_RUN"
    )
    assert group["model_evaluation"] == "REAL_PROVIDER"
    assert (await r.execute(args))["status"] == "ALREADY_COMPLETED"
