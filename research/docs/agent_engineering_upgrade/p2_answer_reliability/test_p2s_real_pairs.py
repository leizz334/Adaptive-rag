"""New P2-S experiment safety tests; never use real credentials or sockets."""

import importlib
import json
import socket
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
MODULE = "research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs"


@pytest.fixture(autouse=True)
def no_network(monkeypatch, event_loop):
    def blocked(*args, **kwargs):
        raise AssertionError("Real sockets forbidden in P2-S harness tests")

    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    yield
    monkeypatch.undo()


@pytest.fixture
def r():
    return importlib.import_module(MODULE)


def payload(**updates):
    return (
        dict(
            model="test",
            messages=[dict(role="user", content="synthetic")],
            temperature=0,
            max_tokens=32,
        )
        | updates
    )


def reply(content="{}", known=True):
    value = dict(
        model="test",
        choices=[
            dict(
                message=dict(content=content, reasoning_content="HIDDEN_REASONING"),
                finish_reason="stop",
            )
        ],
    )
    if known:
        value["usage"] = dict(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    return value


async def post(
    r,
    ledger,
    *,
    body=None,
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
            json=body or payload(),
            headers={"Authorization": "Bearer SECRET_TEST_ONLY"},
        )


def test_new_hard_limits_and_foreign_ledger_rejection(r, tmp_path):
    ledger = r.Ledger(tmp_path)
    assert ledger.limits == {"requests": 350, "tokens": 300000, "usd": 3.0}
    for values in ((351, 0, 0), (0, 300001, 0), (0, 0, 3.01)):
        with pytest.raises(r.SafetyStop):
            ledger.forecast(*values)
    for schema in ("p2r-request-v1", "p2q-request-v1", None):
        r.write(tmp_path / "requests.json", [dict(schema=schema, status="PENDING")])
        with pytest.raises(r.SafetyStop, match="foreign|schema|corrupt"):
            r.Ledger(tmp_path)


@pytest.mark.parametrize("limit", ["requests", "tokens", "usd"])
async def test_each_budget_blocks_before_dispatch(r, tmp_path, limit):
    ledger = r.Ledger(tmp_path, limits={limit: 0})
    with pytest.raises(r.SafetyStop):
        await post(r, ledger, handler=lambda _: pytest.fail("Budget failure reached HTTP"))
    assert ledger.rows == []


async def test_new_namespace_write_ahead_and_public_checkpoint(r, tmp_path):
    def handler(_):
        row = r.read(tmp_path / "requests.json")[-1]
        assert row["status"] == "PENDING" and row["schema"] == "p2s-request-v1"
        assert row["source_sha256"] == "source" and row["config_sha256"] == "config"
        return httpx.Response(200, json=reply())

    await post(r, r.Ledger(tmp_path), handler=handler)
    row = r.read(tmp_path / "requests.json")[-1]
    assert row["status"] == "RESPONSE" and row["latency_ms"] >= 0
    assert "SECRET_TEST_ONLY" not in (tmp_path / "requests.json").read_text()
    assert "HIDDEN_REASONING" not in (tmp_path / "requests.json").read_text()


@pytest.mark.parametrize("kind", ["connect", "timeout", "cancel"])
async def test_uncertain_failure_retains_elapsed_pending_and_never_resends(r, tmp_path, kind):
    import asyncio

    error = {
        "connect": httpx.ConnectError,
        "timeout": httpx.ReadTimeout,
        "cancel": asyncio.CancelledError,
    }[kind]

    def failed(_):
        raise error("private transport detail")

    expected_error = asyncio.CancelledError if kind == "cancel" else r.SafetyStop
    with pytest.raises(expected_error):
        await post(r, r.Ledger(tmp_path), handler=failed)
    ledger = r.Ledger(tmp_path)
    row = ledger.rows[0]
    assert row["status"] == "PENDING" and row["latency_ms"] >= 0
    assert row["transport_error_type"] == error.__name__
    assert "private transport" not in (tmp_path / "requests.json").read_text()
    with pytest.raises(r.SafetyStop, match="uncertain"):
        await post(r, ledger, handler=lambda _: pytest.fail("Uncertain request resent"))


@pytest.mark.parametrize("drift", ["body", "source", "config"])
async def test_completed_replay_binds_all_hashes(r, tmp_path, drift):
    await post(r, r.Ledger(tmp_path))
    await post(r, r.Ledger(tmp_path), handler=lambda _: pytest.fail("Completed response resent"))
    changes = {"body": payload(max_tokens=33)} if drift == "body" else {drift: "different"}
    with pytest.raises(r.SafetyStop, match="hash|fingerprint"):
        await post(r, r.Ledger(tmp_path), **changes)


async def test_usage_unknown_reserves_utf8_and_output_at_frozen_prices(r, tmp_path):
    ledger = r.Ledger(tmp_path, pricing={"input": 2.0, "output": 4.0})
    body = payload(messages=[dict(role="user", content="合成数据")])
    await post(r, ledger, body=body, handler=lambda _: httpx.Response(200, json=reply(known=False)))
    row = ledger.rows[0]
    assert row["reserve_input"] >= len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
    totals = ledger.totals()
    assert totals["accounted_tokens"] == row["reserve_input"] + 32
    assert totals["estimated_usd"] == pytest.approx((row["reserve_input"] * 2 + 32 * 4) / 1000000)


async def test_twenty_fifth_scenario_http_is_blocked(r, tmp_path):
    ledger = r.Ledger(tmp_path)
    await post(r, ledger)
    ledger.rows = [dict(ledger.rows[0], sequence=i) for i in range(24)]
    ledger.save()
    with pytest.raises(r.SafetyStop):
        await post(r, ledger, sequence=24, handler=lambda _: pytest.fail("25th attempt"))


def test_run_lock_rejects_concurrency(r, tmp_path):
    with r.exclusive(tmp_path):
        with pytest.raises(r.SafetyStop, match="concurrency"):
            with r.exclusive(tmp_path):
                pytest.fail("Second run acquired lock")


def test_id_only_selection_has_new_salt(r):
    import hashlib

    ids = [f"synthetic-{i}" for i in range(20)]
    expected = sorted(ids, key=lambda x: hashlib.sha256(("P2S-20261105" + x).encode()).hexdigest())[
        :6
    ]
    assert r.select_blind(ids) == expected == r.select_blind(list(reversed(ids)))
    assert r.DEV_IDS == ["PSD03", "PSD05", "PSD08", "PSD10"]


def test_business_clock_freezes_captured_orm_defaults_and_restores(r):
    from datetime import datetime

    from app.repositories.models import SessionRow

    default = SessionRow.__table__.c.created_at.default
    original = default.arg
    with r.business_clock("2026-11-05T00:00:00+00:00"):
        assert default.arg(None) == datetime.fromisoformat("2026-11-05T00:00:00+00:00")
    assert default.arg is original


async def test_full_mock_prepare_probe_capture_and_crash_resume(r, tmp_path, monkeypatch):
    from argparse import Namespace

    from eval.memory_ablation import ScriptedProvider

    env = tmp_path / "fake.env"
    env.write_text("DEEPSEEK_API_KEY=SYNTHETIC_TEST_ONLY\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SYNTHETIC_TEST_ONLY")
    files = {}
    for split, ids in (
        ("development", r.DEV_IDS),
        ("holdout", [f"synthetic-{i}" for i in range(8)]),
    ):
        path = tmp_path / f"{split}.json"
        r.write(
            path,
            {
                "schema_version": "agent-scenarios-v2.1",
                "scenarios": [
                    dict(
                        id=x,
                        family="synthetic",
                        user_goal="read actual order status",
                        turns=[dict(message="查ORD10003订单状态")],
                    )
                    for x in ids
                ],
            },
        )
        answers = tmp_path / f"{split}_answers.json"
        r.write(
            answers,
            {
                x: [
                    dict(
                        subgoals=["status"],
                        semantic_required=False,
                        facts=[
                            dict(
                                id="paid",
                                goal="status",
                                subject="ORD10003",
                                patterns=["已支付", "paid"],
                                evidence_any_of=[
                                    dict(
                                        tool="get_order",
                                        arguments={"order_id": "ORD10003"},
                                        path="status",
                                        expected="paid",
                                    )
                                ],
                            )
                        ],
                    )
                ]
                for x in ids
            },
        )
        files[split] = (path, answers)
    freeze = tmp_path / "candidate_freeze.json"
    frozen_python = {f"app/module_{i}.py": f"python-{i}" for i in range(128)}
    app_metadata = {f"app/skills/definitions/contract_{i}.json": f"contract-{i}" for i in range(4)}
    r.write(
        freeze,
        dict(
            app_hashes=frozen_python,
            scorer_sha256=r.digest(r.SCORER.read_bytes()),
            app_source_commit="synthetic-candidate",
            datasets={p.name: r.digest(p.read_bytes()) for paths in files.values() for p in paths},
        ),
    )
    monkeypatch.setattr(r, "FREEZE", freeze)
    common = dict(
        files=frozen_python | app_metadata,
        source_sha256="source",
        imports={},
        provider_settings_sha256="settings",
        ambient_settings_sha256="ambient",
        endpoint="https://example.invalid",
        model="test",
        key_recognized=True,
        caps={},
        prompts={},
        signature_caps={},
    )
    snapshots = {"R0": dict(common, head=r.BASE), "R1": dict(common, head="candidate")}
    pending = iter(snapshots.values())
    monkeypatch.setattr(r, "worker_snapshot", lambda *args: next(pending))
    monkeypatch.setattr(r, "fingerprint", lambda *args: snapshots["R0"])
    run = tmp_path / "new-run"
    run.mkdir()
    args = Namespace(
        run_dir=run,
        r0_root=r.SOURCE_ROOT,
        r1_root=r.SOURCE_ROOT,
        env_file=env,
        dev_dataset=files["development"][0],
        dev_answers=files["development"][1],
        blind_dataset=files["holdout"][0],
        blind_answers=files["holdout"][1],
        input_price=0.30,
        output_price=1.20,
        pricing_url="https://example.invalid/pricing",
        pricing_verified_date="2026-11-05",
        variant="R0",
        rep=0,
        case_id="PSD03",
        command="probe",
    )
    with r.exclusive(run):
        assert r.prepare(args)["paid_http_attempts"] == 0
    with pytest.raises(r.SafetyStop, match="overwrite"):
        r.prepare(args)
    script = ScriptedProvider()

    async def answer(request):
        body = json.loads(request.content)
        if body["messages"] == [dict(role="user", content="Reply exactly P2S_OK.")]:
            assert body["max_tokens"] == 32
            content = "P2S_OK"
        else:
            content = (
                await script.generate(body["messages"], response_format=body.get("response_format"))
            ).content
        return httpx.Response(200, json=reply(content))

    monkeypatch.setattr(r.httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(answer))
    assert (await r.execute(args))["status"] == "PROBE_COMPLETE"
    args.command = "run-group"
    args.case_id = "PSD05"
    with pytest.raises(r.SafetyStop, match="order"):
        await r.execute(args)
    args.case_id = "PSD03"
    write = r.write

    def crash(path, value):
        if path.name == "results.json" and value.get("groups"):
            raise KeyboardInterrupt()
        write(path, value)

    monkeypatch.setattr(r, "write", crash)
    with pytest.raises(KeyboardInterrupt):
        await r.execute(args)
    rows = r.Ledger(run).rows
    assert len(rows) > 1 and all(row["status"] == "RESPONSE" for row in rows)
    capture = r.read(run / "captures/PSD03_R0_0.json")
    assert capture["model_evaluation"] == "REAL_PROVIDER"
    assert capture["paid_tokens"] > 0
    assert capture["reported_tokens_group"] >= capture["paid_tokens"]
    assert capture["traces"][0]["turns"][0]["response"]["answer"]
    assert capture["traces"][0]["database_initial"]["tables"]["orders"]
    first_seed_hash = capture["initial_seed_tables_sha256"]
    monkeypatch.setattr(r, "write", write)
    await r.execute(args)
    assert len(r.Ledger(run).rows) == len(rows)
    group = r.read(run / "results.json")["groups"][0]
    assert group["new_http_attempts"] == 0
    assert group["raw_driver_result"]["model_evaluation"] == "NOT_RUN"
    assert group["answer_scores"][0]["ANSWER_COMPLETENESS"] == 1
    assert group["initial_seed_tables_sha256"] == first_seed_hash
    assert (await r.execute(args))["status"] == "ALREADY_COMPLETED"
    args.variant = "R1"
    await r.execute(args)
    paired = r.read(run / "results.json")["groups"]
    assert [g["variant"] for g in paired] == ["R0", "R1"]
    assert paired[1]["initial_seed_tables_sha256"] == first_seed_hash
    before = len(r.Ledger(run).rows)
    monkeypatch.setattr(
        r, "fingerprint", lambda *args: snapshots["R1"] | {"source_sha256": "drift"}
    )
    with pytest.raises(r.SafetyStop, match="fingerprint"):
        await r.execute(args)
    assert len(r.Ledger(run).rows) == before


def test_fresh_worker_binds_application_before_helpers(r, tmp_path):
    import shutil
    import subprocess
    import sys

    for directory in ("app", "eval"):
        shutil.copytree(
            r.HARNESS_ROOT / directory,
            tmp_path / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    completed = subprocess.run(
        [sys.executable, str(HERE / "real_pairs.py"), "_imports", "--source-root", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    bound = json.loads(completed.stdout)
    assert all(Path(path).is_relative_to(tmp_path) for path in bound.values())


async def test_concurrent_request_is_rejected_and_first_keeps_checkpoint(r, tmp_path):
    import asyncio

    started, finish = asyncio.Event(), asyncio.Event()

    async def handler(_):
        started.set()
        await finish.wait()
        return httpx.Response(200, json=reply())

    ledger = r.Ledger(tmp_path)
    task = asyncio.create_task(post(r, ledger, handler=handler))
    await started.wait()
    try:
        with pytest.raises(r.SafetyStop, match="concurrency"):
            await post(r, ledger, handler=lambda _: pytest.fail("Concurrent HTTP"))
    finally:
        finish.set()
        await task
    assert len(ledger.rows) == 1 and ledger.rows[0]["status"] == "RESPONSE"


async def test_non200_is_saved_but_stops_provider_fallback_calls(r, tmp_path):
    with pytest.raises(r.SafetyStop, match="HTTP error"):
        await post(r, r.Ledger(tmp_path), handler=lambda _: httpx.Response(429, json=reply()))
    row = r.Ledger(tmp_path).rows[0]
    assert row["status"] == "RESPONSE" and row["model_error"] == "http_429"


def test_independent_scoring_keeps_tool_environment_and_semantics_separate(r):
    raw = dict(reasons=[], metrics={"environment_state_correct": 0}, evidence={"tool_calls": []})
    evidence = dict(
        results=[raw],
        traces=[
            dict(
                turns=[
                    dict(turn=0, nodes=[], response=dict(answer="请明确订单号。"), final_state={})
                ]
            )
        ],
    )
    gold = [
        dict(
            subgoals=["clarify"],
            facts=[dict(id="clarify", goal="clarify", patterns=["请明确订单号"])],
            expected_abstention=True,
            semantic_required=False,
        )
    ]
    result = r.score_captured(evidence, gold)[0]
    assert result["TOOL_SUCCESS"] == "PASS" and result["ENVIRONMENT_SUCCESS"] == "FAIL"
    assert result["OVERALL_TASK_SUCCESS"] == "FAIL"
    assert result["semantic_human_calibration"] == "NOT_RUN"


def test_signature_caps_record_actual_judge_default(r, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app/example.py").write_text(
        "def judge(*,max_tokens=512):\n    pass\n", encoding="utf-8"
    )
    assert r.signature_caps(tmp_path) == {"app/example.py": ["judge:Constant(value=512)"]}


def test_python_freeze_accepts_all_128_python_and_four_unchanged_json_contracts(r):
    python = {f"app/module_{i}.py": f"candidate-python-{i}" for i in range(128)}
    metadata = {f"app/skills/definitions/contract_{i}.json": f"contract-{i}" for i in range(4)}
    snapshots = {
        "R0": {"files": {**{p: "baseline-python" for p in python}, **metadata}},
        "R1": {"files": {**python, **metadata}},
    }
    r.verify_application_freeze(snapshots, {"app_hashes": python})
    assert len(snapshots["R1"]["files"]) == 132


def test_python_freeze_still_rejects_changed_missing_or_added_app_json_contracts(r):
    python = {"app/example.py": "candidate-python"}
    metadata = {"app/skills/definitions/order_tracking.json": "unchanged"}
    for changed in (
        {"app/skills/definitions/order_tracking.json": "changed"},
        {},
        metadata | {"app/skills/definitions/new.json": "added"},
    ):
        snapshots = {"R0": {"files": python | metadata}, "R1": {"files": python | changed}}
        with pytest.raises(r.SafetyStop, match="non-Python|contract|metadata"):
            r.verify_application_freeze(snapshots, {"app_hashes": python})
