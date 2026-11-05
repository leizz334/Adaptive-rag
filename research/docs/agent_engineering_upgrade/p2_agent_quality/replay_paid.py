"""Offline exact-response replay of completed paid groups; never sends HTTP.

Run this absolute file in a fresh process with --source-root before app imports.
Only groups already persisted as completed are eligible. A hash mismatch fails
closed and leaves the actual final service answer unknown.
"""

# ruff: noqa: E402 -- source binding must precede app/eval imports.
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

HARNESS_ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--source-root", type=Path)
_binding, _ = _parser.parse_known_args()
SOURCE_ROOT = (_binding.source_root or HARNESS_ROOT).resolve()
sys.path.insert(0, str(SOURCE_ROOT))
for _name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_name] = "false"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load_module("_p2r_replay_frozen_helpers", HERE.parent / "p2_quality/real.py")
capture = load_module("_p2r_replay_capture", HERE / "instrumented.py")

import httpx

from app.config.settings import Settings
from app.providers.deepseek import DeepSeekProvider

SafetyStop = old.SafetyStop
ORIGIN = "LOCAL_REPLAY_OF_COMPLETED_PAID_RESPONSES"


class ReplayLLM(DeepSeekProvider):
    """Actual source provider, exclusively backed by a strict MockTransport."""

    def __init__(self, settings, rows):
        if any(row.get("status") != "RESPONSE" or "response" not in row for row in rows):
            raise SafetyStop("only completed durable responses are eligible")
        if [row["sequence"] for row in rows] != list(range(len(rows))):
            raise SafetyStop("completed request sequence is not contiguous")
        self.rows, self.sequence, self.failure = rows, 0, None
        self.client = httpx.AsyncClient(
            base_url=settings.deepseek_base_url.rstrip("/"),
            transport=httpx.MockTransport(self.reply),
            timeout=30,
        )
        super().__init__(
            settings.model_copy(update={"llm_max_retries": 1, "llm_timeout_seconds": 30.0}),
            client=self.client,
        )

    def reply(self, request):
        try:
            body = json.loads(request.content)
        except ValueError:
            raise SafetyStop("non-JSON replay request") from None
        actual = old.digest({"method": request.method, "url": str(request.url), "body": body})
        if self.sequence >= len(self.rows):
            self.failure = {
                "sequence": self.sequence,
                "actual_sha256": actual,
                "kind": "missing_completed_response",
            }
            raise SafetyStop("missing completed response; no live transport exists")
        row = self.rows[self.sequence]
        if actual != row["request_sha256"]:
            self.failure = {
                "sequence": self.sequence,
                "stage": row.get("stage"),
                "expected_sha256": row["request_sha256"],
                "actual_sha256": actual,
                "kind": "request_hash_mismatch",
            }
            raise SafetyStop("request sequence hash mismatch; final answer unknown")
        self.sequence += 1
        return httpx.Response(row["http_status"], json=row["response"], request=request)

    async def generate(self, messages, *, temperature=0.0, max_tokens=1024, response_format=None):
        return await super().generate(
            messages,
            temperature=0.0,
            max_tokens=min(max_tokens, 1024),
            response_format=response_format,
        )

    async def aclose(self):
        await self.client.aclose()


def oracle_outcome(row):
    return {
        "status": row["status"],
        "reasons": row["reasons"],
        "environment_state_correct": row["metrics"]["environment_state_correct"],
        "turns": [
            {key: turn[key] for key in ("turn", "error", "scores", "pending", "refused")}
            for turn in row["evidence"]["turns"]
        ],
    }


def answer_stages(trace):
    value = []
    for turn in trace["turns"]:
        generated = next(
            (
                node.get("output", {}).get("final_answer")
                for node in turn["nodes"]
                if node["node"] == "generate_answer"
            ),
            None,
        )
        final = turn.get("response", {}).get("answer")
        value.append(
            {
                "turn": turn["turn"],
                "generated_answer": generated,
                "final_service_answer": final,
                "changed_after_generate": final != generated
                if final is not None and generated is not None
                else None,
                "service_error": turn.get("error"),
            }
        )
    return value


async def replay(args):
    with capture.offline_network():
        return await _replay(args)


async def _replay(args):
    run = args.run_dir.resolve()
    if args.output.resolve().is_relative_to(run):
        raise SafetyStop("replay output must be outside the immutable live run directory")
    paths = {
        name: run / name for name in ("experiment_config.json", "requests.json", "results.json")
    }
    before = {name: old.digest(path.read_bytes()) for name, path in paths.items()}
    config, ledger, live = (old.read(paths[name]) for name in paths)
    if (
        old.digest({key: value for key, value in config.items() if key != "config_sha256"})
        != config["config_sha256"]
    ):
        raise SafetyStop("frozen live configuration hash conflict")
    snapshot = config["snapshots"][args.variant]
    if SOURCE_ROOT != Path(config["roots"][args.variant]).resolve():
        raise SafetyStop("variant source root differs from frozen live root")
    for module_name in ("app.config.settings", "app.providers.deepseek", "eval.multiturn"):
        if not Path(sys.modules[module_name].__file__).resolve().is_relative_to(SOURCE_ROOT):
            raise SafetyStop("application/evaluator bound to the wrong source root")
    for name, expected in snapshot["files"].items():
        if old.digest((SOURCE_ROOT / name).read_bytes()) != expected:
            raise SafetyStop("frozen production source mismatch: " + name)
    groups = [
        group
        for group in live["groups"]
        if group["variant"] == args.variant and group["status"] in {"PASS", "FAIL"}
    ]
    settings = Settings(
        _env_file=None,
        app_env="testing",
        deepseek_api_key="synthetic-offline-replay-only",
        deepseek_base_url=snapshot["endpoint"],
        deepseek_model=snapshot["model"],
        llm_max_retries=1,
        agent_tracing_enabled=False,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    summaries = []
    metadata = {
        "evidence_origin": ORIGIN,
        "variant": args.variant,
        "source_root": str(SOURCE_ROOT),
        "source_sha256": snapshot["source_sha256"],
        "live_artifact_hashes": before,
        "network": "FORBIDDEN_MOCK_TRANSPORT_ONLY",
        "historical_trace": False,
        "new_paid_api_calls": 0,
        "new_paid_tokens": 0,
        "usage_note": "Any usage in replayed service traces belongs to already billed durable responses; never add it to global usage totals.",
        "excluded_pending_groups": sorted(
            {row["group"] for row in ledger if row["status"] != "RESPONSE"}
        ),
    }
    capture.write_new(args.output / "replay_config.json", metadata)
    try:
        for index, group in enumerate(groups):
            rows = [row for row in ledger if row["group"] == group["group"]]
            provider = None
            summary = {
                "group": group["group"],
                "case_id": group["case_id"],
                "variant": args.variant,
                "original_status": group["status"],
                "evidence_origin": ORIGIN,
            }
            try:
                if any(
                    row.get("source_sha256") != snapshot["source_sha256"]
                    or row.get("config_sha256") != config["config_sha256"]
                    for row in rows
                ):
                    raise SafetyStop("completed row source/config binding mismatch")
                dataset = config["datasets"][group["split"]]
                raw = Path(dataset["path"]).read_bytes()
                if old.digest(raw) != dataset["sha256"]:
                    raise SafetyStop("frozen dataset hash mismatch")
                # Materialize only this already-completed case; never validate or
                # run any uncompleted held-out case.
                from eval.multiturn import Scenario

                case = Scenario.model_validate(
                    next(
                        row for row in json.loads(raw)["scenarios"] if row["id"] == group["case_id"]
                    )
                )
                provider = ReplayLLM(settings, rows)
                with patch(
                    "app.services.seed.utcnow",
                    return_value=datetime.fromisoformat(config["seed_clock"]),
                ):
                    value = await capture.evaluate_cases(
                        [case],
                        dataset_sha256=dataset["sha256"],
                        provider="replay",
                        llm_factory=lambda value=provider: value,
                    )
                if provider.sequence != len(rows):
                    raise SafetyStop("replay ended before consuming the entire completed sequence")
                value["evidence_origin"] = ORIGIN
                for trace in value["traces"]:
                    trace["evidence_origin"] = ORIGIN
                summary.update(
                    status="EXACT_REPLAY_COMPLETE",
                    replayed_responses=provider.sequence,
                    oracle_equivalent=oracle_outcome(value["results"][0])
                    == oracle_outcome(group["raw_driver_result"]),
                    answer_stages=answer_stages(value["traces"][0]),
                )
                capture.write_new(args.output / f"{index:02d}_trace.json", value)
            except SafetyStop as exc:
                summary.update(
                    status="UNKNOWN_FINAL_ANSWER",
                    replay_error=str(exc),
                    failure=provider.failure if provider else None,
                    consumed_responses=provider.sequence if provider else 0,
                )
            finally:
                if provider is not None:
                    await provider.aclose()
            summaries.append(summary)
            capture.write_new(args.output / f"{index:02d}_summary.json", summary)
    finally:
        after = {name: old.digest(path.read_bytes()) for name, path in paths.items()}
        capture.write_new(
            args.output / "validation.json",
            {
                "live_artifacts_unchanged": before == after,
                "live_artifact_hashes_after": after,
                "new_paid_api_calls": 0,
                "new_paid_tokens": 0,
            },
        )
        if before != after:
            raise SafetyStop(
                "live journal changed during local replay; no journal writes were performed by this helper"
            )
    result = metadata | {
        "groups": summaries,
        "complete": sum(row["status"] == "EXACT_REPLAY_COMPLETE" for row in summaries),
        "unknown": sum(row["status"] != "EXACT_REPLAY_COMPLETE" for row in summaries),
    }
    capture.write_new(args.output / "results.json", result)
    return {key: result[key] for key in ("variant", "complete", "unknown", "new_paid_api_calls")}


def synthetic_row():
    payload = {
        "model": "synthetic",
        "messages": [{"role": "user", "content": "synthetic"}],
        "temperature": 0.0,
        "max_tokens": 32,
    }
    return {
        "group": "synthetic:R0:0",
        "sequence": 0,
        "status": "RESPONSE",
        "http_status": 200,
        "request_sha256": old.digest(
            {"method": "POST", "url": "https://replay.invalid/chat/completions", "body": payload}
        ),
        "response": {
            "model": "synthetic",
            "choices": [{"message": {"content": "synthetic answer"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
    }


async def test_replay_provider_uses_only_exact_mock_response_and_forces_actual_temperature():
    settings = Settings(
        _env_file=None,
        deepseek_api_key="synthetic-never-real",
        deepseek_base_url="https://replay.invalid",
        deepseek_model="synthetic",
    )
    provider = ReplayLLM(settings, [synthetic_row()])
    with capture.offline_network():
        value = await provider.generate(
            [{"role": "user", "content": "synthetic"}], temperature=0.8, max_tokens=32
        )
    assert value.content == "synthetic answer" and value.usage.total_tokens == 12
    assert provider.sequence == 1 and isinstance(provider.client._transport, httpx.MockTransport)
    await provider.aclose()


async def test_replay_matches_wire_bytes_from_actual_frozen_provider():
    settings = Settings(
        _env_file=None,
        deepseek_api_key="synthetic-never-real",
        deepseek_base_url="https://replay.invalid",
        deepseek_model="synthetic",
        llm_max_retries=1,
    )
    requests = []
    row = synthetic_row()

    def record(request):
        requests.append(request)
        return httpx.Response(200, json=row["response"], request=request)

    with capture.offline_network():
        async with httpx.AsyncClient(
            base_url=settings.deepseek_base_url, transport=httpx.MockTransport(record)
        ) as client:
            frozen = old.Provider.__new__(old.Provider)
            old.DeepSeekProvider.__init__(frozen, settings, client=client)
            await frozen.generate([{"role": "user", "content": "synthetic"}], max_tokens=32)
        original = requests[0]
        assert b'"temperature":0.0' in original.content
        row["request_sha256"] = old.digest(
            {
                "method": original.method,
                "url": str(original.url),
                "body": json.loads(original.content),
            }
        )
        replayed = ReplayLLM(settings, [row])
        try:
            value = await replayed.generate(
                [{"role": "user", "content": "synthetic"}], max_tokens=32
            )
            assert value.content == "synthetic answer" and replayed.sequence == 1
        finally:
            await replayed.aclose()


async def test_replay_hash_mismatch_and_missing_response_bypass_application_fallback():
    import pytest

    settings = Settings(
        _env_file=None,
        deepseek_api_key="synthetic-never-real",
        deepseek_base_url="https://replay.invalid",
        deepseek_model="synthetic",
    )
    provider = ReplayLLM(settings, [synthetic_row()])
    with capture.offline_network():
        with pytest.raises(SafetyStop, match="hash"):
            await provider.generate([{"role": "user", "content": "different"}], max_tokens=32)
        assert provider.sequence == 0
        await provider.generate([{"role": "user", "content": "synthetic"}], max_tokens=32)
        with pytest.raises(SafetyStop, match="missing"):
            await provider.generate([{"role": "user", "content": "synthetic"}], max_tokens=32)
    await provider.aclose()


def test_pending_is_never_eligible_for_local_replay():
    import pytest

    with pytest.raises(SafetyStop, match="completed"):
        ReplayLLM(Settings(_env_file=None), [synthetic_row() | {"status": "PENDING"}])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant", choices=["R0", "R1"], required=True)
    parser.add_argument("--run-dir", type=Path, default=HERE / "runs/20261105_R5_pairs_01")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    print(json.dumps(asyncio.run(replay(args))))


if __name__ == "__main__":
    main()
