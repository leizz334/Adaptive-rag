"""Experiment-only metering; unchanged P1 service, fixtures, Gold and scorers."""

# ruff: noqa: I001 -- importing baseline first disables external tracing before app imports.

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import math
import platform
import time
from datetime import datetime
from pathlib import Path
from statistics import mean
from unittest.mock import patch

from research.docs.agent_engineering_upgrade.real_llm_baseline import baseline as b

import httpx

from app.core.exceptions import LLMProviderError
from app.providers.deepseek import DeepSeekProvider
from eval.multiturn import load_scenarios, run_scenarios


def read(run: Path, name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def write(run: Path, name: str, value):
    target = run / name
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    tmp.replace(target)


def usage_total(row):
    usage = row.get("usage")
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    if not isinstance(usage, dict) or not all(
        type(usage.get(k)) is int and usage[k] >= 0 for k in keys
    ):
        return None
    return (
        usage["total_tokens"]
        if usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
        else None
    )


class Ledger:
    def __init__(self, run: Path, config: dict):
        self.run, self.config = run, config
        self.rows = read(run, "requests.json")
        self.stop_reason: str | None = None

    @property
    def accounted_tokens(self):
        return sum(
            usage_total(r) if usage_total(r) is not None else r["reserved_tokens"]
            for r in self.rows
        )

    def save(self):
        write(self.run, "requests.json", self.rows)

    def fail(self, kind: str, row=None):
        self.stop_reason = kind
        if row is not None:
            row["failure"] = kind
        self.save()
        raise LLMProviderError("Experiment stopped: " + kind, retryable=False)


class MeteredDeepSeek(DeepSeekProvider):
    def __init__(self, settings, ledger: Ledger, case_id: str, *, transport=None):
        self.ledger, self.case_id = ledger, case_id
        self.row = None
        self.started = 0.0
        self.original_temperature = 0.0
        self.client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=3.0, read=settings.llm_timeout_seconds, write=10.0, pool=5.0
            ),
            transport=transport,
            event_hooks={"request": [self.before], "response": [self.after]},
        )
        super().__init__(settings, client=self.client)

    async def aclose(self):
        await self.client.aclose()

    async def before(self, request):
        body = json.loads(request.content)
        reserve = len(request.content) + 1024 + body["max_tokens"]
        if self.ledger.stop_reason:
            self.ledger.fail(self.ledger.stop_reason)
        if len(self.ledger.rows) >= self.ledger.config["max_http_attempts"]:
            self.ledger.fail("request_budget_exhausted")
        if self.ledger.accounted_tokens + reserve > self.ledger.config["max_accounted_tokens"]:
            self.ledger.fail("token_budget_reservation_exhausted")
        self.started = time.perf_counter()
        self.row = {
            "phase": "scenario",
            "case_id": self.case_id,
            "started_at": b.stamp(),
            "status": "IN_FLIGHT",
            "model_requested": body["model"],
            "temperature": body["temperature"],
            "original_requested_temperature": self.original_temperature,
            "max_tokens": body["max_tokens"],
            "input_bytes": len(request.content),
            "reserved_tokens": reserve,
            "request_sha256": hashlib.sha256(request.content).hexdigest(),
        }
        self.ledger.rows.append(self.row)
        self.ledger.save()

    async def after(self, response):
        await response.aread()
        row = self.row
        row.update(
            status="HTTP_RESPONSE",
            http_status=response.status_code,
            latency_ms=(time.perf_counter() - self.started) * 1000,
            response_sha256=hashlib.sha256(response.content).hexdigest(),
            content_type=response.headers.get("content-type"),
        )
        self.ledger.save()
        if response.status_code != 200:
            self.ledger.fail("api_http_" + str(response.status_code), row)
        try:
            payload = response.json()
        except ValueError:
            self.ledger.fail("api_invalid_json", row)
        if not isinstance(payload, dict):
            self.ledger.fail("api_invalid_shape", row)
        row["model_reported"] = payload.get("model")
        raw = payload.get("usage")
        usage = (
            {k: raw.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            if isinstance(raw, dict)
            else None
        )
        row["usage"] = usage
        if not usage or not all(type(v) is int and v >= 0 for v in usage.values()):
            self.ledger.fail("api_missing_or_invalid_usage", row)
        if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
            self.ledger.fail("api_inconsistent_usage", row)
        if self.ledger.accounted_tokens > self.ledger.config["max_accounted_tokens"]:
            self.ledger.fail("api_usage_exceeds_budget", row)
        row["finish_reasons"] = [c.get("finish_reason") for c in payload.get("choices", [])]
        self.ledger.save()

    async def generate(self, messages, *, temperature=0.0, max_tokens=1024, response_format=None):
        if self.ledger.stop_reason:
            self.ledger.fail(self.ledger.stop_reason)
        if not 0 < max_tokens <= 1024:
            self.ledger.fail("invalid_output_budget")
        self.original_temperature = temperature
        self.row = None
        try:
            value = await super().generate(
                messages, temperature=0.0, max_tokens=max_tokens, response_format=response_format
            )
        except Exception as exc:
            if self.row is not None:
                self.row["error_chain"] = b.exception_diagnostic(exc)
                self.row["latency_ms"] = (time.perf_counter() - self.started) * 1000
                if "failure" not in self.row:
                    self.row["failure"] = (
                        "api_timeout"
                        if any(x["type"].endswith("Timeout") for x in self.row["error_chain"])
                        else "api_transport_or_response_error"
                    )
                    self.ledger.stop_reason = self.row["failure"]
                self.ledger.save()
            raise
        self.row["status"] = "COMPLETED"
        if response_format and response_format.get("type") == "json_object":
            try:
                self.row["model_json_object_valid"] = isinstance(json.loads(value.content), dict)
            except ValueError:
                self.row["model_json_object_valid"] = False
        self.ledger.save()
        return value


async def evaluate(run: Path):
    config, result = read(run, "experiment_config.json"), read(run, "results.json")
    if not result["connectivity"]["connected"]:
        raise SystemExit("Connectivity gate failed; do not run scenarios.")
    if result.get("evaluation_started_at"):
        raise SystemExit(
            "Scenario execution already started; inspect saved partial results, no replay."
        )
    assert all(b.sha(b.ROOT / path) == digest for path, digest in config["frozen_files"].items())
    settings = b.isolated_settings()
    assert settings.deepseek_base_url == config["endpoint"]
    assert settings.deepseek_model == config["configured_model"]
    cases, digest = load_scenarios(b.DATASET)
    assert digest == config["dataset_sha256"]
    indexed = {c.id: c for c in cases}
    ledger = Ledger(run, config)
    config["evaluation_harness_sha256"] = b.sha(Path(__file__))
    config["runtime_versions"] = {
        name: importlib.metadata.version(name)
        for name in ("httpx", "pydantic", "pydantic-settings", "langgraph", "sqlalchemy")
    }
    config["python_version"] = platform.python_version()
    config["fixture_seed_time_utc"] = config["created_at"]
    write(run, "experiment_config.json", config)
    result.update(status="RUNNING", evaluation_started_at=b.stamp(), results=[])
    write(run, "results.json", result)
    started = time.perf_counter()
    for case_id in config["selected_case_ids"]:
        if ledger.stop_reason:
            break
        before = len(ledger.rows)
        try:
            # Freeze synthetic order timestamps without changing the fixture or production source.
            with patch(
                "app.services.seed.utcnow",
                return_value=datetime.fromisoformat(config["fixture_seed_time_utc"]),
            ):
                values = await run_scenarios(
                    [indexed[case_id]],
                    dataset_sha256=digest,
                    tracing=False,
                    llm_factory=lambda case_id=case_id: MeteredDeepSeek(settings, ledger, case_id),
                )
            value = values[0].model_dump()
            value["p1_driver_status"] = value["status"]
            value["model_evaluation"] = "REAL_PROVIDER_PRODUCTION_SERVICE"
            value["api_request_count"] = len(ledger.rows) - before
            value["model_invoked"] = value["api_request_count"] > 0
            value["api_errors"] = [r["failure"] for r in ledger.rows[before:] if r.get("failure")]
            if value["api_errors"] or ledger.stop_reason:
                value["status"] = "ERROR"
                value["reasons"].append("real_model_validity_gate:" + str(ledger.stop_reason))
        except Exception as exc:
            value = {
                "case_id": case_id,
                "status": "ERROR",
                "reasons": ["infrastructure_error"],
                "error_chain": b.exception_diagnostic(exc),
                "metrics": {},
                "evidence": {},
            }
            ledger.stop_reason = "infrastructure_error"
        result["results"].append(value)
        result["stop_reason"] = ledger.stop_reason
        result["evaluation_latency_ms"] = (time.perf_counter() - started) * 1000
        write(run, "results.json", result)
        print(
            json.dumps(
                {
                    "case_id": case_id,
                    "status": value["status"],
                    "requests_so_far": len(ledger.rows),
                    "accounted_tokens": ledger.accounted_tokens,
                }
            ),
            flush=True,
        )
    attempted = {v["case_id"] for v in result["results"]}
    result["results"].extend(
        {"case_id": c, "status": "NOT_RUN", "reasons": [ledger.stop_reason or "not_executed"]}
        for c in config["selected_case_ids"]
        if c not in attempted
    )
    result.update(
        status="PARTIAL" if ledger.stop_reason else "COMPLETED", evaluation_finished_at=b.stamp()
    )
    write(run, "results.json", result)


def summarize(run: Path):
    c, result, rows = (
        read(run, "experiment_config.json"),
        read(run, "results.json"),
        read(run, "requests.json"),
    )
    done = [r for r in result["results"] if r["status"] != "NOT_RUN"]
    valid = [r for r in done if r["status"] != "ERROR"]
    turns = [t for r in valid for t in r["evidence"]["turns"]]
    arguments = [
        t["scores"]["tool_argument_accuracy"]
        for t in turns
        if t["scores"]["tool_argument_accuracy"] is not None
    ]
    env = [r["metrics"]["environment_state_correct"] for r in valid]
    refs = [r for r in valid if r["case_id"] in c["reference_case_ids"]]
    ref_ok = sum(
        r["status"] != "ERROR"
        and r["evidence"]["turns"][-1]["scores"]["trajectory_valid"] == 1
        and r["evidence"]["turns"][-1]["scores"]["tool_argument_accuracy"] == 1
        and r["evidence"]["turns"][-1]["error"] is None
        for r in refs
    )
    safety_tags = (
        "forbidden_",
        "unconfirmed_write",
        "cross_user_tool_output",
        "protected_order_field",
        "preexisting_row_changed",
        "order_created_or_deleted",
    )
    safety = [
        {"case_id": r["case_id"], "reason": reason}
        for r in done
        for reason in r.get("reasons", [])
        if any(tag in reason for tag in safety_tags)
    ]
    latencies = sorted(
        r["metrics"]["latency_ms"] for r in done if "latency_ms" in r.get("metrics", {})
    )
    complete_usage = bool(rows) and all(usage_total(r) is not None for r in rows)
    summary = {
        "selected_cases": len(c["selected_case_ids"]),
        "attempted_cases": len(done),
        "valid_cases": len(valid),
        "passed": sum(r["status"] == "PASS" for r in done),
        "task_success_rate": sum(r["status"] == "PASS" for r in valid) / len(valid)
        if valid
        else None,
        "end_to_end_success_rate_including_errors": sum(r["status"] == "PASS" for r in done)
        / len(done)
        if done
        else None,
        "reference_evaluated": len(refs),
        "reference_correct": ref_ok,
        "reference_resolution": ref_ok / len(refs) if refs else None,
        "tool_selection_accuracy": mean(t["scores"]["tool_selection_accuracy"] for t in turns)
        if turns
        else None,
        "tool_selection_turns": len(turns),
        "tool_argument_accuracy": mean(arguments) if arguments else None,
        "tool_argument_turns": len(arguments),
        "environment_success": mean(env) if env else None,
        "environment_evaluated": len(env),
        "safety_violations": safety if valid or safety else None,
        "safety_evaluated_cases": len(valid),
        "mean_case_latency_ms": mean(latencies) if latencies else None,
        "p95_case_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1]
        if latencies
        else None,
        "total_tokens": sum(usage_total(r) for r in rows) if complete_usage else None,
        "reported_tokens_lower_bound": sum(usage_total(r) or 0 for r in rows),
        "http_requests": len(rows),
        "api_failures": sum(bool(r.get("failure")) for r in rows),
        "api_timeouts": sum(r.get("failure") == "api_timeout" for r in rows),
        "model_json_format_errors": sum(r.get("model_json_object_valid") is False for r in rows),
        "infrastructure_errors": sum("infrastructure_error" in r.get("reasons", []) for r in done),
        "models_reported": sorted({r["model_reported"] for r in rows if r.get("model_reported")}),
        "evaluation_latency_ms": result.get("evaluation_latency_ms"),
        "case_api_request_counts": {r["case_id"]: r.get("api_request_count") for r in done},
        "baseline_reproducible": result["status"] == "COMPLETED"
        and not any(r["status"] == "ERROR" for r in done),
    }
    result["summary"] = summary
    write(run, "results.json", result)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "summary"])
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    if args.command == "run":
        asyncio.run(evaluate(args.run_dir))
    else:
        print(json.dumps(summarize(args.run_dir), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
