"""Pinned P6 context comparison with actual session replay and the P5 billing ledger."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from contextlib import ExitStack, contextmanager
from decimal import Decimal
from functools import wraps
from pathlib import Path
from unittest.mock import patch

from app.agents import graph
from app.repositories.models import SessionRow
from app.repositories.session_repository import SessionRepository
from eval.release.shared import run_p5 as replay
from eval.release.shared.score_p5 import latency

HERE = Path(__file__).resolve().parent
ROOT = HERE.relative_to(HERE.parents[2])
BASE = "0b0f2405f55ccc4df5b59a7bcd17a6b56784dc34"
FIXTURE_SHA = "bfad92b58f77ae2233e8bf784cb5bea79c3924fcf7d88ed2edf4d3ecbb8dddd2"
CAP_CNY = Decimal("0.20")
MAX_REQUESTS = 80
ARMS = ("A", "E")
OTHER_STAGES = {
    "router_node": "router",
    "retrieval_node": "retrieval",
    "generate_node": "answer",
    "faithfulness_node": "faithfulness",
    "memory_node": "memory",
    "executor_node": "executor",
}
COHORTS = ("context_long", "context_correction", "context_continuation", "context_constraint")
P5_ROOT = Path("artifacts/hybrid_planner/p5")


def fixtures():
    path = HERE / "fixtures.json"
    cases, digest = replay.load_scenarios(path)
    data = replay.read_report(path)
    oracles = data["oracles"]
    if digest != FIXTURE_SHA or {case.id for case in cases} != oracles.keys():
        raise replay.RunStopped("Frozen context scenarios changed")
    for gold in oracles.values():
        prelude = gold["prelude"]
        lead = prelude.get("lead", [])
        segment = data["history_segments"][prelude["segment"]] if "segment" in prelude else []
        gold["prelude_messages"] = [*lead, *segment]
    return {case.id: case for case in cases}, oracles, digest


def verify_harness(commit):
    files = (
        ROOT / "run_p6.py",
        ROOT / "fixtures.json",
        P5_ROOT / "run_p5.py",
        P5_ROOT / "score_p5.py",
        Path("artifacts/hybrid_planner/p3_5/budget.py"),
    )
    verified = {}
    source = HERE.parents[2]
    for path in files:
        current = source.joinpath(path).read_bytes().replace(b"\r\n", b"\n")
        expected = replay.blob(commit, path).replace(b"\r\n", b"\n")
        if current != expected:
            raise replay.RunStopped(f"Context replay input differs from Git: {path.as_posix()}")
        verified[path.as_posix()] = replay.digest(current)
    return verified


def _timed_node(operation, stage):
    @wraps(operation)
    async def observed(*args, **kwargs):
        with replay.stage(stage):
            return await operation(*args, **kwargs)

    return observed


_observe_p5 = replay.observe_graph
_execute_p5 = replay.execute
_environment_p5 = replay.BusinessEnvironment


@contextmanager
def observe_graph():
    with _observe_p5(), ExitStack() as patches:
        for name, stage in OTHER_STAGES.items():
            if operation := getattr(graph, name, None):
                patches.enter_context(patch.object(graph, name, _timed_node(operation, stage)))
        yield


def summary_state(text):
    if not text:
        return {"bytes": 0, "version": None, "coverage_message_id": None, "revision": None}
    try:
        data = json.loads(text)
    except ValueError:
        data = {}
    return {
        "bytes": len(text.encode("utf-8")),
        "version": data.get("version"),
        "coverage_message_id": data.get("coverage_message_id"),
        "revision": data.get("revision"),
        "keys": sorted(data),
        "envelope": data,
    }


async def execute(case, oracle, arm, repeat, llm, ledger):
    """Seed the public session history. Production determines context on every target turn."""
    session_id = f"p6_{case.id}"
    prelude = oracle["prelude_messages"]
    captures = []

    class SeededEnvironment(_environment_p5):
        async def __aenter__(self):
            await super().__aenter__()
            try:
                async with self.container.session_factory() as db:
                    repo = SessionRepository(db)
                    await repo.get_or_create(session_id, case.user_id)
                    for role, content in prelude:
                        await repo.append_message(session_id, role, content)
                    await db.commit()
            except BaseException:
                await self.__aexit__()
                raise

            original = self.service.chat

            async def observe_chat(request, *, trace_id):
                if not captures:
                    request = request.model_copy(update={"session_id": session_id})
                before = await self._get_summary(session_id)
                try:
                    return await original(request, trace_id=trace_id)
                finally:
                    captures.append(
                        {
                            "session_id": request.session_id,
                            "summary_before": before,
                            "summary_after": await self._get_summary(session_id),
                        }
                    )

            self.service.chat = observe_chat
            return self

        async def _get_summary(self, session):
            async with self.container.session_factory() as db:
                row = await db.get(SessionRow, session)
                return summary_state(row.summary if row is not None else None)

    with patch.object(replay, "BusinessEnvironment", SeededEnvironment):
        result = await _execute_p5(case, oracle, arm, repeat, llm, ledger)
    result["prelude"] = {
        "messages": len(prelude),
        "user_messages": sum(role == "user" for role, _ in prelude),
        "utf8_bytes": sum(len(content.encode("utf-8")) for _, content in prelude),
        "sha256": replay.digest(json.dumps(prelude, ensure_ascii=False).encode("utf-8")),
    }
    for turn, capture in zip(result["turns"], captures, strict=True):
        turn["request"]["session_id"] = capture.pop("session_id")
        turn.update(capture)
        turn["context_views"] = [
            span["metadata"] for span in turn["spans"] if span["name"] == "memory.context_view"
        ]
    return result


def context_ids(turn):
    context = turn.get("context") or {}
    bound = {context.get("order_id"), context.get("product_sku")}
    bound.update(goal.get("entity_id") for goal in turn["goals"] if not goal.get("negated"))
    return {item for item in bound if item}


def assess_case(row, oracle):
    turns = []
    for observed, score in zip(row["turns"], row["scores"]["turns"], strict=True):
        gold = oracle["turns"].get(str(observed["index"]), {})
        expected = set(gold.get("entity", {}).values()) | set(gold.get("entities", []))
        actual = context_ids(observed)
        before = observed["summary_before"]
        after = observed["summary_after"]
        turns.append(
            {
                "index": observed["index"],
                "expected_entities": sorted(expected),
                "actual_entities": sorted(actual),
                "entity_ok": actual == expected if expected else None,
                "missing_entities": sorted(expected - actual),
                "wrong_entities": sorted(actual - expected) if expected else [],
                "answer_checks": score["answer_checks"],
                "condition_checks": score["conditions"],
                "state_unchanged": observed["state_unchanged"],
                "compaction_advanced": (after["coverage_message_id"] or 0)
                > (before["coverage_message_id"] or 0),
                "compacted_summary_bytes_before": before["bytes"],
                "compacted_summary_bytes_after": after["bytes"],
                "views": observed["context_views"],
            }
        )
    return {"strict": row["scores"]["success"], "reasons": row["scores"]["reasons"], "turns": turns}


def usage(receipts):
    counts = Counter()
    for receipt in receipts:
        counts.update(receipt["usage"] or {})
    return {
        "calls": len(receipts),
        "usage": dict(counts),
        "cost_cny": replay.cny(sum(receipt["tariff_nano_cny"] for receipt in receipts)),
        "latency_ms": latency(
            [item["latency_ms"] for item in receipts if item["latency_ms"] is not None]
        ),
    }


def summary(cases, oracles, rows, receipts, totals):
    indexed = {receipt["id"]: receipt for receipt in receipts}
    runs = {arm: [row for row in rows if row["arm"] == arm] for arm in ARMS}
    groups, cases_view = {}, {}
    for arm, run in runs.items():
        observed = [turn for row in run for turn in row["turns"]]
        ids = {key for turn in observed for key in turn["request_ids"]}
        http = [item for item in receipts if item["id"] in ids]
        names = sorted({item["scope"]["stage"] for item in http})
        cases_view[arm] = {row["case"]: assess_case(row, oracles[row["case"]]) for row in run}
        assertions = [turn for item in cases_view[arm].values() for turn in item["turns"]]
        groups[arm] = {
            "all": replay.metric_group(run, indexed),
            "cohorts": {
                segment: replay.metric_group(
                    [row for row in run if row["cohort"] == segment], indexed
                )
                for segment in COHORTS
            },
            "node_usage": {
                name: usage([item for item in http if item["scope"]["stage"] == name])
                for name in names
            },
            "context_entity_turns": sum(item["entity_ok"] is not None for item in assertions),
            "context_entity_correct": sum(item["entity_ok"] is True for item in assertions),
            "compaction_advances": sum(item["compaction_advanced"] for item in assertions),
        }
    matched = set(cases_view["A"]) & set(cases_view["E"])
    linked = {key for row in rows for turn in row["turns"] for key in turn["request_ids"]}
    return {
        "schema": "p6_context_comparison_v1",
        "ledger": totals,
        "tariff_cost_cny": replay.cny(sum(item["tariff_nano_cny"] for item in receipts)),
        "models": dict(
            Counter(
                item["response"].get("model", "unknown") for item in receipts if item["response"]
            )
        ),
        "paired_primary_cases": sorted(matched),
        "primary_complete": len(matched) == len(cases),
        "paired_pass_changes": {
            "gains": sorted(
                key
                for key in matched
                if not cases_view["A"][key]["strict"] and cases_view["E"][key]["strict"]
            ),
            "losses": sorted(
                key
                for key in matched
                if cases_view["A"][key]["strict"] and not cases_view["E"][key]["strict"]
            ),
        },
        "groups": groups,
        "cases": cases_view,
        "unlinked_receipts": sorted(set(indexed) - linked),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--arm", choices=ARMS)
    mode.add_argument("--collect", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--harness-commit")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--block", type=int, choices=(0, 1))
    parser.add_argument("--cap-cny", default=str(CAP_CNY))
    parser.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    options = parser.parse_args()
    if not 0 < Decimal(options.cap_cny) <= CAP_CNY or not 0 < options.max_requests <= MAX_REQUESTS:
        parser.error("The combined P6 replay cannot exceed ¥0.20 and 80 HTTP attempts")
    if options.dry_run and not options.arm:
        parser.error("Dry run requires an arm")
    options.repeat = False
    isolated = {
        name: value
        for name, value in os.environ.items()
        if name.lower() not in replay.Settings.model_fields or name.lower() == "deepseek_api_key"
    }
    isolated.update(LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    with (
        patch.object(replay, "PINNED", {"A": BASE}),
        patch.object(replay, "ARMS", ARMS),
        patch.object(replay, "FROZEN_FIXTURE_SHA", FIXTURE_SHA),
        patch.object(replay, "fixtures", fixtures),
        patch.object(replay, "verify_harness", verify_harness),
        patch.object(replay, "observe_graph", observe_graph),
        patch.object(replay, "execute", execute),
        patch.object(replay, "summary", summary),
        patch.dict(os.environ, isolated, clear=True),
    ):
        asyncio.run(replay.run(options))


if __name__ == "__main__":
    main()
