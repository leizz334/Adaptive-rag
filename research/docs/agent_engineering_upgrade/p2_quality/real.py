"""Bounded paired real-provider experiment. No application or Gold changes.

Run with ``python -m research.docs.agent_engineering_upgrade.p2_quality.real``.
One run directory owns the global paid ledger, including probe and later retests.
"""

# ruff: noqa: E402 -- disable external tracing before framework imports.
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import logging
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

for _name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_name] = "false"

import httpx

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider
from eval.environment import BusinessEnvironment
from eval.multiturn import load_scenarios, run_scenarios

ROOT = Path(__file__).resolve().parents[4]
BASE = "c45f509f5e4260c34818df9bf48f2807dd1338b4"
DATASET = ROOT / "eval/dataset/agent_v2_extended.json"
REFERENCE = ["context_loss"] + [
    f"freshness_ORD1000{i}_pronoun_{state}" for i in (1, 2, 3) for state in ("stable", "changed")
]
SELECTED = ["order_lookup"] + REFERENCE + ["explicit_target_change", "greeting"]
LIMITS = {"requests": 350, "tokens": 300_000, "usd": 3.0}
INPUT_PRICE, OUTPUT_PRICE = 0.30 / 1_000_000, 1.20 / 1_000_000


class SafetyStop(BaseException):
    """Bypass application fallback handlers when paid execution must stop."""


def stamp():
    return datetime.now(UTC).isoformat()


def digest(value):
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def exclusive(run):
    """OS lock releases on crash; stale lock file never requires deleting state."""
    run.mkdir(parents=True, exist_ok=True)
    with (run / ".lock").open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SafetyStop("concurrency lock: another runner owns this ledger") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def usage(raw):
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    if not isinstance(raw, dict) or not all(type(raw.get(k)) is int and raw[k] >= 0 for k in keys):
        return None
    if raw["total_tokens"] != raw["prompt_tokens"] + raw["completion_tokens"]:
        return None
    if raw["prompt_tokens"] <= 0 or raw["total_tokens"] <= 0:
        return None
    return {k: raw[k] for k in keys}


class Ledger:
    def __init__(self, run, *, limits=None):
        self.run = Path(run)
        self.limits = LIMITS | (limits or {})
        if any(self.limits[k] > v or self.limits[k] < 0 for k, v in LIMITS.items()):
            raise SafetyStop("invalid hard budget")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []

    def save(self):
        write(self.path, self.rows)

    def totals(self):
        tokens, usd, reported = 0, 0.0, 0
        for row in self.rows:
            raw = usage(row.get("usage"))
            prompt = raw["prompt_tokens"] if raw else row["reserve_input"]
            output = raw["completion_tokens"] if raw else row["reserve_output"]
            tokens += prompt + output
            reported += raw["total_tokens"] if raw else 0
            usd += prompt * INPUT_PRICE + output * OUTPUT_PRICE
        return {
            "http_attempts": len(self.rows),
            "accounted_tokens": tokens,
            "reported_tokens": reported,
            "estimated_usd": usd,
            "unknown_usage_requests": sum(usage(r.get("usage")) is None for r in self.rows),
        }

    def forecast(self, requests, tokens, usd):
        totals = self.totals()
        if (
            totals["http_attempts"] + requests > self.limits["requests"]
            or totals["accounted_tokens"] + tokens > self.limits["tokens"]
            or totals["estimated_usd"] + usd > self.limits["usd"]
        ):
            raise SafetyStop("group forecast exceeds remaining budget")

    def check_pending(self):
        if any(row["status"] != "RESPONSE" for row in self.rows):
            raise SafetyStop(
                "uncertain HTTP attempt; durable response absent; manual reconciliation required"
            )


def public_response(response):
    """Whitelist public completions/usage only; never persist raw HTTP/error bodies."""
    try:
        body = response.json()
    except ValueError:
        return {"choices": [], "usage": None}, "invalid_http_json"
    if not isinstance(body, dict):
        return {"choices": [], "usage": None}, "invalid_http_shape"
    choices = []
    for choice in body.get("choices", []) if isinstance(body.get("choices"), list) else []:
        if isinstance(choice, dict):
            message = choice.get("message") or {}
            choices.append(
                {
                    "message": {
                        "content": message.get("content") if isinstance(message, dict) else None
                    },
                    "finish_reason": choice.get("finish_reason"),
                }
            )
    clean = {"model": body.get("model"), "choices": choices, "usage": usage(body.get("usage"))}
    if (
        clean["usage"]
        and clean["usage"]["completion_tokens"] == 0
        and any(c["message"]["content"] for c in choices)
    ):
        clean["usage"] = None
    error = None
    if not choices or not isinstance(choices[0]["message"]["content"], str):
        error = "invalid_completion_shape"
    elif any(c["finish_reason"] == "length" for c in choices):
        error = "truncated"
    return clean, error


def stage_metadata(body):
    system = next((m.get("content", "") for m in body["messages"] if m.get("role") == "system"), "")
    prompts = (
        ("intent", "INTENT_SYSTEM", "intent"),
        ("complexity", "COMPLEXITY_SYSTEM", "router"),
        ("planner", "PLANNER_SYSTEM", "planner"),
        ("answer", "ANSWER_SYSTEM", "generate"),
        ("faithfulness", "FAITHFULNESS_SYSTEM", "judge"),
        ("faithfulness", "SELF_CORRECT_SYSTEM", "self_correct"),
        ("query_rewrite", "REWRITE_SYSTEM", "rewrite"),
        ("self_rag", "GRADE_SYSTEM", "grade"),
        ("summary", "SUMMARY_SYSTEM", "summary"),
    )
    stage = "unknown"
    for module, name, label in prompts:
        template = getattr(importlib.import_module("app.prompts." + module), name, "")
        if template and system.startswith(template.split("{", 1)[0]):
            stage = label
            break
    return {
        "stage": stage,
        "available_tool_names": sorted(set(re.findall(r"(?m)^- ([a-z][a-z_]+):", system)))
        if stage == "planner"
        else [],
    }


class ReplayTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger, group, underlying=None):
        self.ledger, self.group = ledger, group
        self.underlying = underlying or httpx.AsyncHTTPTransport(retries=0)
        self.sequence = 0

    async def handle_async_request(self, request):
        ledger = self.ledger
        ledger.check_pending()
        body = json.loads(request.content)
        if body.get("temperature") != 0 or not 0 < body.get("max_tokens", 0) <= 1024:
            raise SafetyStop("request differs from frozen temperature/output constraints")
        request_hash = digest({"method": request.method, "url": str(request.url), "body": body})
        rows = [row for row in ledger.rows if row["group"] == self.group]
        index = self.sequence
        self.sequence += 1
        if index < len(rows):
            row = rows[index]
            if row["request_sha256"] != request_hash:
                raise SafetyStop("request sequence hash conflict; replay forbidden")
            return httpx.Response(row["http_status"], json=row["response"], request=request)
        reserve_input, reserve_output = len(request.content) + 1024, body["max_tokens"]
        try:
            ledger.forecast(
                1,
                reserve_input + reserve_output,
                reserve_input * INPUT_PRICE + reserve_output * OUTPUT_PRICE,
            )
        except SafetyStop as exc:
            raise SafetyStop("request budget reservation exhausted") from exc
        row = {
            "group": self.group,
            "sequence": index,
            "status": "PENDING",
            "started_at": stamp(),
            "request_sha256": request_hash,
            "prompt_sha256": digest(body["messages"]),
            "reserve_input": reserve_input,
            "reserve_output": reserve_output,
            "max_tokens": reserve_output,
            "temperature": 0,
            "usage": None,
            **stage_metadata(body),
        }
        ledger.rows.append(row)
        ledger.save()  # Write-ahead reservation precedes dispatch, including timeouts.
        started = time.perf_counter()
        try:
            response = await self.underlying.handle_async_request(request)
            await response.aread()
        except Exception as exc:
            row["transport_error_type"] = type(exc).__name__
            ledger.save()
            raise SafetyStop("uncertain HTTP transport result; never retry automatically") from None
        clean, error = public_response(response)
        if response.status_code != 200:
            clean, error = (
                {"choices": [], "usage": clean.get("usage")},
                f"http_{response.status_code}",
            )
        elif body.get("response_format", {}).get("type") == "json_object" and not error:
            try:
                if not isinstance(json.loads(clean["choices"][0]["message"]["content"]), dict):
                    error = "invalid_json_object"
            except (ValueError, TypeError):
                error = "invalid_json_object"
        row.update(
            status="RESPONSE",
            http_status=response.status_code,
            response=clean,
            usage=clean.get("usage"),
            model_error=error,
            latency_ms=(time.perf_counter() - started) * 1000,
            completed_at=stamp(),
        )
        ledger.save()  # Checkpoint response before provider parsing or downstream task work.
        totals = ledger.totals()
        if (
            totals["accounted_tokens"] > ledger.limits["tokens"]
            or totals["estimated_usd"] > ledger.limits["usd"]
        ):
            raise SafetyStop("provider-reported usage exceeds reservation/budget; stop")
        return httpx.Response(response.status_code, json=clean, request=request)

    async def aclose(self):
        await self.underlying.aclose()


class Provider(DeepSeekProvider):
    def __init__(self, settings, ledger, group):
        self.client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url.rstrip("/"),
            timeout=30,
            transport=ReplayTransport(ledger, group),
        )
        super().__init__(settings, client=self.client)

    async def generate(self, messages, *, temperature=0.0, max_tokens=1024, response_format=None):
        return await super().generate(
            messages, temperature=0.0, max_tokens=max_tokens, response_format=response_format
        )

    async def aclose(self):
        await self.client.aclose()


def settings(env_file):
    actual = Settings(_env_file=env_file)
    return actual.model_copy(
        update={"llm_max_retries": 1, "llm_timeout_seconds": 30.0, "agent_tracing_enabled": False}
    )


def settings_fingerprint(value):
    # Pydantic masks SecretStr; persist only a hash, never URLs/credentials/settings text.
    return digest(json.loads(value.model_dump_json()))


def source_files():
    return {
        p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
        for directory in ("app", "eval", "knowledge")
        for p in sorted((ROOT / directory).rglob("*"))
        if p.is_file() and p.suffix in {".py", ".json", ".md", ".yaml", ".yml"}
    }


def prepare(run, env_file):
    if any(
        (run / name).exists()
        for name in ("experiment_config.json", "requests.json", "results.json")
    ):
        raise SafetyStop("prepare would overwrite existing experiment; preserve ledger")
    config_settings = settings(env_file)
    frozen = source_files()
    for path, hash_value in frozen.items():
        original = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
        if digest(original) != hash_value:
            raise SafetyStop("original P2 source differs: " + path)
    cases, dataset_hash = load_scenarios(DATASET)
    if not set(SELECTED) <= {c.id for c in cases}:
        raise SafetyStop("selected cases absent")
    config = {
        "schema": "p2q-real-v1",
        "created_at": stamp(),
        "source_base": BASE,
        "frozen_files": frozen,
        "harness_sha256": digest(Path(__file__).read_bytes()),
        "dataset_sha256": dataset_hash,
        "selected_ids": SELECTED,
        "reference_ids": REFERENCE,
        "modes": ["M0", "M1", "M2"],
        "mode_order": "cyclic rotation per case: M0/M1/M2, M1/M2/M0, M2/M0/M1",
        "endpoint": config_settings.deepseek_base_url,
        "model": config_settings.deepseek_model,
        "limits": LIMITS,
        "temperature": 0,
        "http_attempts_per_call": 1,
        "concurrency": 1,
        "input_usd_per_million": 0.30,
        "output_usd_per_million": 1.20,
        "pricing_url": "https://api-docs.deepseek.com/quick_start/pricing/",
        "pricing_verified_date": "2026-11-04",
        "key_recognized": config_settings.llm_configured,
        "provider_settings_sha256": settings_fingerprint(config_settings),
        "ambient_settings_sha256": settings_fingerprint(Settings(_env_file=None)),
        "prompt_files": {p: h for p, h in frozen.items() if p.startswith("app/prompts/")},
    }
    config["config_sha256"] = digest(config)
    write(run / "experiment_config.json", config)
    write(run / "requests.json", [])
    write(run / "results.json", {"probe": None, "groups": [], "status": "PREPARED"})
    return {"status": "PREPARED", "key_recognized": config_settings.llm_configured}


def verify(run, env_file):
    config = read(run / "experiment_config.json")
    actual = settings(env_file)
    if (
        digest({k: v for k, v in config.items() if k != "config_sha256"}) != config["config_sha256"]
        or source_files() != config["frozen_files"]
        or digest(Path(__file__).read_bytes()) != config["harness_sha256"]
        or actual.deepseek_base_url != config["endpoint"]
        or actual.deepseek_model != config["model"]
        or settings_fingerprint(actual) != config["provider_settings_sha256"]
        or settings_fingerprint(Settings(_env_file=None)) != config["ambient_settings_sha256"]
        or config["limits"] != LIMITS
        or config["selected_ids"] != SELECTED
        or config["modes"] != ["M0", "M1", "M2"]
        or digest(DATASET.read_bytes()) != config["dataset_sha256"]
    ):
        raise SafetyStop("frozen source/config hash conflict")
    if not actual.llm_configured:
        raise SafetyStop("explicit env file has no configured key")
    return config, actual


def summarize(groups, ledger):
    arms = {}
    for mode in ("M0", "M1", "M2"):
        rows = [g for g in groups if g["mode"] == mode]
        http_errors = [
            g for g in rows if any(e.startswith("http_") for e in g.get("request_errors", []))
        ]
        model_errors = [
            g for g in rows if any(not e.startswith("http_") for e in g.get("request_errors", []))
        ]
        valid = [g for g in rows if not g.get("request_errors") and g["status"] != "ERROR"]
        arms[mode] = {
            "attempted_groups": len(rows),
            "passed": sum(g["status"] == "PASS" for g in rows),
            "task_success_including_errors": sum(g["status"] == "PASS" for g in rows) / len(rows)
            if rows
            else None,
            "task_success_valid_outputs": sum(g["status"] == "PASS" for g in valid) / len(valid)
            if valid
            else None,
            "http_error_groups": len(http_errors),
            "model_invalid_groups": len(model_errors),
        }
    return {
        "arms": arms,
        "requests": ledger.totals(),
        "limits": ledger.limits,
        "pricing": "peak, no cache discounts; estimate not invoice",
    }


async def execute(command, run, env_file):
    config, actual = verify(run, env_file)
    result = read(run / "results.json")
    ledger = Ledger(run)
    ledger.check_pending()
    if command == "probe":
        if result["probe"] is not None:
            raise SafetyStop("probe already completed; inspect result")
        provider = Provider(actual, ledger, "probe")
        try:
            response = await provider.generate(
                [{"role": "user", "content": "Reply exactly P2Q_OK."}], max_tokens=32
            )
            result["probe"] = {
                "connected": True,
                "completion_valid": response.content.strip() == "P2Q_OK",
                "model": response.model,
            }
        except Exception as exc:
            rows = [row for row in ledger.rows if row["group"] == "probe"]
            result["probe"] = {
                "connected": bool(rows and rows[-1].get("http_status") == 200),
                "completion_valid": False,
                "error_type": type(exc).__name__,
            }
        finally:
            await provider.aclose()
        write(run / "results.json", result)
        return result["probe"]
    if not result["probe"] or not result["probe"]["connected"]:
        raise SafetyStop("successful single probe required")
    cases, dataset_hash = load_scenarios(DATASET)
    by_id = {case.id: case for case in cases}
    planned = [
        (case_id, config["modes"][(index + offset) % 3])
        for index, case_id in enumerate(config["selected_ids"])
        for offset in range(3)
    ]
    completed = {(g["case_id"], g["mode"]) for g in result["groups"]}
    pilot = set(planned[:3])
    if command in {"run", "resume"} and not pilot <= completed:
        raise SafetyStop("complete one three-mode pilot before continuation")
    target = planned[:3] if command == "pilot" else planned
    for case_id, mode in target:
        if (case_id, mode) in completed:
            continue
        # Reserve a conservative next-group forecast from observed group maxima.
        previous = result["groups"]
        count = max([g["request_count"] for g in previous] or [12])
        bound = max([g["reserved_tokens"] for g in previous] or [24_000])
        existing = [r for r in ledger.rows if r["group"] == case_id + ":" + mode]
        if not existing:
            ledger.forecast(count, bound, bound * OUTPUT_PRICE)
        provider = Provider(actual, ledger, case_id + ":" + mode)

        def environment(memory_mode=mode, **kwargs):
            return BusinessEnvironment(memory_mode=memory_mode, **kwargs)

        try:
            with (
                patch("eval.multiturn.BusinessEnvironment", environment),
                patch(
                    "app.services.seed.utcnow",
                    return_value=datetime.fromisoformat(config["created_at"]),
                ),
            ):
                values = await run_scenarios(
                    [by_id[case_id]],
                    dataset_sha256=dataset_hash,
                    tracing=False,
                    llm_factory=lambda provider=provider: provider,
                )
            group = values[0].model_dump()
        finally:
            await provider.aclose()
        rows = [r for r in ledger.rows if r["group"] == case_id + ":" + mode]
        if provider.client._transport.sequence != len(rows):
            raise SafetyStop("replay ended before stored request sequence; hash conflict")
        group.update(
            mode=mode,
            request_count=len(rows),
            request_errors=[r["model_error"] for r in rows if r.get("model_error")],
            reserved_tokens=sum(r["reserve_input"] + r["reserve_output"] for r in rows),
        )
        if any(error.startswith("http_") for error in group["request_errors"]):
            group["driver_status"] = group["status"]
            group["status"] = "ERROR"
        result["groups"].append(group)
        result["status"] = "PILOT_COMPLETE" if command == "pilot" else "RUNNING"
        result["summary"] = summarize(result["groups"], ledger)
        write(run / "results.json", result)
        print(
            json.dumps(
                {"case": case_id, "mode": mode, "status": group["status"], **ledger.totals()}
            ),
            flush=True,
        )
        if group["request_errors"] and any(e.startswith("http_") for e in group["request_errors"]):
            raise SafetyStop("HTTP error saved; stop without retries")
    if len(result["groups"]) == len(planned):
        result["status"] = "COMPLETED"
        write(run / "results.json", result)
    return result["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "probe", "pilot", "run", "resume", "summary"]
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--env-file", required=True, type=Path, help="explicit root .env; never serialized"
    )
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        with exclusive(args.run_dir):
            if args.command == "prepare":
                value = prepare(args.run_dir, args.env_file)
            elif args.command == "summary":
                value = summarize(
                    read(args.run_dir / "results.json")["groups"], Ledger(args.run_dir)
                )
            else:
                value = asyncio.run(execute(args.command, args.run_dir, args.env_file))
            print(json.dumps(value, ensure_ascii=True, indent=2))
    except SafetyStop as exc:
        print("STOP: " + str(exc))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
