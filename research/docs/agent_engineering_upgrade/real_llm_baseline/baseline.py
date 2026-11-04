"""Explicit, resumable experiment commands. No production business infrastructure."""

# ruff: noqa: E402 -- tracing must be disabled before importing application/frameworks.

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

# No external tracing, including framework auto-instrumentation.
for _name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_name] = "false"

import httpx
from pydantic import SecretStr

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider
from app.services.container import build_container
from eval.multiturn import load_scenarios

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
STATE = OUT.parent
DATASET = ROOT / "eval/dataset/agent_v2_extended.json"
REFERENCE_IDS = ["context_loss"] + [
    f"freshness_{order}_pronoun_{change}"
    for order in ("ORD10001", "ORD10002", "ORD10003")
    for change in ("stable", "changed")
]
CONTROL_IDS = [
    "order_lookup",
    "explicit_target_change",
    "greeting",
    "argument_binding",
    "cancel_pending",
    "foreign_order",
    "cross_user_session",
    "injection",
]


def stamp():
    return datetime.now(UTC).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = OUT / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def isolated_settings():
    # Read .env through the application's actual loader. Never serialize Settings.
    actual = Settings()
    return actual.model_copy(
        update={
            "app_env": "testing",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "redis_url": "",
            "qdrant_url": "",
            "embedding_api_key": SecretStr(""),
            "embedding_base_url": "",
            "local_embedding_enabled": False,
            "local_embedding_force": False,
            "cross_encoder_enabled": False,
            "cross_encoder_force": False,
            "unstructured_enabled": False,
            "unstructured_force": False,
            "mcp_enabled": False,
            "mcp_remote_url": "",
            "agent_tracing_enabled": False,
            "agent_tracing_backend": "local",
            "llm_max_retries": 1,
            "llm_timeout_seconds": 30.0,
            "knowledge_dir": str(ROOT / "knowledge"),
        }
    )


def prepare():
    if (OUT / "experiment_config.json").exists():
        raise SystemExit("Config already frozen; inspect artifacts instead of overwriting.")
    s = isolated_settings()
    cases, digest = load_scenarios(DATASET)
    selected = REFERENCE_IDS + CONTROL_IDS
    assert len(selected) == len(set(selected)) == 15
    assert set(selected) <= {c.id for c in cases}
    frozen = {}
    for directory in ("app", "knowledge", "eval"):
        for p in sorted((ROOT / directory).rglob("*")):
            if p.is_file() and (p.suffix in {".py", ".md", ".json", ".yaml", ".yml"}):
                frozen[p.relative_to(ROOT).as_posix()] = sha(p)
    for p in (STATE / "P1_REPORT.md", STATE / "evidence/P1-F-extended-1.json"):
        frozen[p.relative_to(ROOT).as_posix()] = sha(p)
    write(
        "experiment_config.json",
        {
            "schema_version": "real-baseline-v1",
            "created_at": stamp(),
            "baseline_git_head": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "initial_working_tree": git("status", "--short"),
            "conda_environment": "adaptive-rag",
            "endpoint": s.deepseek_base_url,
            "configured_model": s.deepseek_model,
            "key_recognized": s.llm_configured,
            "provenance": "User-approved third-party gateway; underlying DeepSeek identity unverified",
            "dataset_path": str(DATASET.relative_to(ROOT)),
            "dataset_sha256": digest,
            "dataset_schema": "agent-scenarios-v2.1",
            "selected_case_ids": selected,
            "reference_case_ids": REFERENCE_IDS,
            "frozen_files": frozen,
            "temperature": 0.0,
            "max_output_tokens_per_request": 1024,
            "max_http_attempts": 80,
            "max_accounted_tokens": 100000,
            "concurrency": 1,
            "http_attempts_per_call": 1,
            "read_timeout_seconds": 30,
            "scoring": "Unchanged eval.multiturn.run_scenarios, eval.tool_scoring.score_tools, eval.goal_scoring.score_goal",
            "reference_metric": "Last-turn trajectory valid and tool argument accuracy == 1 for the seven frozen reference cases; tool-grounded resolution, not semantic answer judging",
            "isolation": "Fresh SQLite :memory: per case, synthetic seed; no remote DB/Redis/Qdrant/MCP; retrieval fallback matches P1 offline fixtures",
            "tracing": "disabled; no external tracing; synthetic prompt/response hashes only",
            "probe_messages": [
                {
                    "role": "user",
                    "content": "Reply with exactly BASELINE_OK. This is a read-only connectivity check.",
                }
            ],
            "probe_max_tokens": 32,
        },
    )
    write("requests.json", [])
    write("results.json", {"status": "PREPARED", "connectivity": None, "results": []})
    print("Configuration frozen; key_recognized=" + str(s.llm_configured))


def exception_diagnostic(exc):
    # Exception strings and bodies may reflect secrets. Keep typed causes/codes only.
    chain = []
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        chain.append(
            {
                "type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
                "winerror": getattr(exc, "winerror", None),
            }
        )
        exc = exc.__cause__ or exc.__context__
    return chain


class BudgetExceeded(Exception):
    """Raised before transport when the frozen request/token ceiling is reached."""


class UsageAccountingError(Exception):
    """A gateway response cannot provide trustworthy usage accounting."""


async def probe(*, network_retry=False):
    config = read("experiment_config.json")
    result = read("results.json")
    records = read("requests.json")
    initial_count = len(records)
    permission_block = records and any(
        e["type"] == "PermissionError" and e.get("winerror") == 5
        for e in records[-1].get("error_chain", [])
    )
    if (records or result["connectivity"] is not None) and not (
        network_retry and permission_block and len(records) == 1
    ):
        raise SystemExit(
            "Probe already attempted; inspect persisted result, no automatic paid replay."
        )
    s = isolated_settings()
    assert (
        s.deepseek_base_url == config["endpoint"] and s.deepseek_model == config["configured_model"]
    )
    result["connectivity"] = {"key_recognized": s.llm_configured, "official_api_verified": False}
    started = time.perf_counter()
    request_started = started

    async def request_hook(request):
        nonlocal request_started
        request_started = time.perf_counter()
        body = json.loads(request.content)
        reservation = len(request.content) + 1024 + body["max_tokens"]
        accounted = sum(
            (r.get("usage") or {}).get("total_tokens", r["reserved_tokens"]) for r in records
        )
        if len(records) >= config["max_http_attempts"] or (
            accounted + reservation > config["max_accounted_tokens"]
        ):
            raise BudgetExceeded("Frozen experiment budget exhausted")
        records.append(
            {
                "phase": "connectivity",
                "started_at": stamp(),
                "status": "IN_FLIGHT",
                "model_requested": body["model"],
                "request_sha256": hashlib.sha256(request.content).hexdigest(),
                "input_bytes": len(request.content),
                "max_tokens": body["max_tokens"],
                "reserved_tokens": reservation,
            }
        )
        write("requests.json", records)

    async def response_hook(response):
        await response.aread()
        record = records[-1]
        record.update(
            {
                "http_status": response.status_code,
                "latency_ms": (time.perf_counter() - request_started) * 1000,
                "status": "HTTP_RESPONSE",
                "content_type": response.headers.get("content-type"),
                "response_bytes": len(response.content),
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
            }
        )
        write("requests.json", records)
        if response.status_code == 200:
            payload = response.json()
            raw_usage = payload.get("usage")
            usage = (
                {
                    k: raw_usage.get(k)
                    for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                }
                if isinstance(raw_usage, dict)
                else None
            )
            record.update(
                {
                    "model_reported": payload.get("model"),
                    "usage": usage,
                    "response_sha256": hashlib.sha256(response.content).hexdigest(),
                    "finish_reasons": [x.get("finish_reason") for x in payload.get("choices", [])],
                }
            )
            write("requests.json", records)
            if not usage or not all(type(v) is int and v >= 0 for v in usage.values()):
                raise UsageAccountingError("Missing or invalid gateway usage")
            if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
                raise UsageAccountingError("Inconsistent gateway usage")
            accounted = sum(
                (r.get("usage") or {}).get("total_tokens", r["reserved_tokens"]) for r in records
            )
            if accounted > config["max_accounted_tokens"]:
                raise UsageAccountingError("Gateway-reported usage exceeded frozen budget")
        write("requests.json", records)

    client = httpx.AsyncClient(
        base_url=s.deepseek_base_url.rstrip("/"),
        timeout=httpx.Timeout(30.0, connect=3.0),
        event_hooks={"request": [request_hook], "response": [response_hook]},
    )
    container = None
    try:
        # Exercise actual application's provider selection, using isolated infrastructure.
        container = await build_container(s, seed=False)
        result["connectivity"]["application_provider"] = type(container.llm).__name__
        assert isinstance(
            container.llm, DeepSeekProvider
        ), "Configured key did not select real provider"
        await container.llm.aclose()
        provider = DeepSeekProvider(s, client=client)
        response = await provider.generate(
            config["probe_messages"], temperature=0.0, max_tokens=config["probe_max_tokens"]
        )
        connected = bool(records and records[-1].get("http_status") == 200 and response.content)
        result["connectivity"].update(
            {
                "connected": connected,
                "probe_expected_text_received": response.content.strip() == "BASELINE_OK",
                "model_reported": records[-1].get("model_reported"),
                "usage": records[-1]["usage"],
            }
        )
        result["status"] = "CONNECTED" if connected else "BLOCKED_CONNECTIVITY"
    except Exception as exc:
        if len(records) > initial_count:
            records[-1].update(
                {
                    "error_chain": exception_diagnostic(exc),
                    "latency_ms": (time.perf_counter() - request_started) * 1000,
                }
            )
            if records[-1]["status"] == "IN_FLIGHT":
                records[-1]["status"] = "TRANSPORT_ERROR"
        result["connectivity"].update(
            {"connected": False, "error_chain": exception_diagnostic(exc)}
        )
        result["status"] = (
            "BLOCKED_ACCOUNTING"
            if isinstance(exc, UsageAccountingError | BudgetExceeded)
            else "BLOCKED_CONNECTIVITY"
        )
    finally:
        if container:
            await container.aclose()
        await client.aclose()
        result["connectivity"]["latency_ms"] = (time.perf_counter() - started) * 1000
        write("requests.json", records)
        write("results.json", result)
    print(json.dumps(result["connectivity"], ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "probe", "probe-network"])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    else:
        asyncio.run(probe(network_retry=args.command == "probe-network"))


if __name__ == "__main__":
    main()
