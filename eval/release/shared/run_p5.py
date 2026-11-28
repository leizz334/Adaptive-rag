"""Budgeted P5 full-graph DeepSeek replay against immutable Git archives."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import httpx

import app
from app.agents.nodes.intent import IntentClassifier
from app.agents.nodes.planner import Planner
from app.config.settings import Settings
from app.core.exceptions import AppError, LLMOutputError
from app.observability.execution import capture_tools
from app.observability.tracing import TraceRecorder
from app.providers.deepseek import DeepSeekProvider
from app.providers.json_parser import extract_json_object
from app.repositories.models import OrderRow
from app.schemas.agent import AgentPlan
from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment
from eval.multiturn import load_scenarios
from eval.release.shared.budget import (
    HOST,
    MODEL,
    RATE,
    REQUEST_SCOPE,
    Ledger,
    MeteredTransport,
    RunStopped,
    append_jsonl,
    cny,
    metered_usage,
)
from eval.release.shared.score_p5 import metric_group, score_case

HERE = Path(__file__).resolve().parent
ROOT = HERE.relative_to(HERE.parents[2])
CLOCK = datetime(2026, 11, 25, 1, tzinfo=UTC)
TAIPEI = timezone(timedelta(hours=8))
PINNED = {
    "A": "38c4e2071cb9f9c8fc04ee9f834fe2635b88aea9",
    "B": "284fa3d53f1f356e6101cf4ffb72012cd6609035",
    "C": "2a7872e9a64a4ce2b46165e17cf6d89ad55b1664",
    "D": "c80b4996a5eb928bc7025363e859f88a5f5dfff9",
}
ARMS = (*PINNED, "E")
REPEAT_ARMS = ("D", "E")
MAX_CNY = Decimal("3.20")
MAX_REQUESTS = 260
HARNESS = ("run_p5.py", "score_p5.py", "fixtures.json")
FROZEN_FIXTURE_SHA = "8de94b08e12cf3836e59870783b53d79cc5ed1653cea7cf0697d86f79f04837a"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_output(*cmd):
    return subprocess.check_output(["git", *cmd])


def blob(commit, filename):
    return git_output("cat-file", "blob", f"{commit}:{filename.as_posix()}")


def check_commit(commit):
    if (
        not commit
        or len(commit) != 40
        or git_output("rev-parse", commit).decode().strip() != commit
    ):
        raise RunStopped("A full pinned Git commit is required")


def verify_source(commit):
    root = Path.cwd().resolve()
    if Path(app.__file__).resolve().parent != root / "app":
        raise RunStopped("App imports must resolve to the selected Git archive")
    listing = git_output("ls-tree", "-r", "-z", commit, "--", "app", "eval", "knowledge")
    files = {}
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        info, filename = entry.decode("utf-8").split("\t", 1)
        _, kind, expected = info.split()
        source = (root / filename).read_bytes()
        actual = hashlib.sha1(f"blob {len(source)}\0".encode() + source).hexdigest()
        if kind != "blob" or actual != expected:
            raise RunStopped(f"Pinned source differs from Git at {filename}")
        files[filename] = digest(source)
    if not files:
        raise RunStopped("Pinned app/eval/knowledge files are missing")
    return files


def verify_harness(commit):
    verified = {}
    for filename in HARNESS:
        actual = (HERE / filename).read_bytes().replace(b"\r\n", b"\n")
        expected = blob(commit, ROOT / filename).replace(b"\r\n", b"\n")
        if actual != expected:
            raise RunStopped(f"Evaluation inputs differ from the pinned Git blob: {filename}")
        verified[filename] = digest(actual)
    return verified


def fixtures():
    path = HERE / "fixtures.json"
    cases, fixtures_digest = load_scenarios(path)
    if fixtures_digest != FROZEN_FIXTURE_SHA:
        raise RunStopped("Independent P5 gold changed after fixture freeze")
    oracles = json.loads(path.read_bytes())["oracles"]
    if {case.id for case in cases} != oracles.keys():
        raise RunStopped("Case IDs differ from the frozen annotation manifest")
    return {case.id: case for case in cases}, oracles, fixtures_digest


def scheduled(cases, oracles, arm, block, repeat):
    ids = list(cases)
    if repeat:
        return [key for key in ids if arm in REPEAT_ARMS and oracles[key].get("repeat") == 2]
    block_ids = ids if block is None else ids[block::2]
    offset = ARMS.index(arm) % len(block_ids)
    return block_ids[offset:] + block_ids[:offset]


def save(destination, value):
    """Create reports without overwriting or opening an ambiguous resume."""
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def read_report(path):
    return json.loads(path.read_bytes())


def read_rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()] if path.is_file() else []


def serial(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [serial(item) for item in value]
    return value


class ComparingTransport(MeteredTransport):
    """Pin model thinking on the common wire without replacing any Planner or provider."""

    async def handle_async_request(self, request):
        original = json.loads(await request.aread())
        original["thinking"] = {"type": "disabled"}
        headers = httpx.Headers(request.headers)
        headers.pop("content-length", None)
        adjusted = httpx.Request(
            request.method,
            request.url,
            headers=headers,
            json=original,
            extensions=request.extensions,
        )
        return await super().handle_async_request(adjusted)


@contextmanager
def stage(name):
    scope = REQUEST_SCOPE.get()
    if scope is None:
        yield
        return
    previous = scope["stage"]
    scope["stage"] = name
    try:
        yield
    finally:
        scope["stage"] = previous


@contextmanager
def observe_graph():
    classify = IntentClassifier.classify
    method = "_create_plan" if hasattr(Planner, "_create_plan") else "create_plan"
    plan = getattr(Planner, method)

    async def observe_intent(self, *args, **kwargs):
        with stage("intent"):
            return await classify(self, *args, **kwargs)

    async def observe_plan(self, *args, **kwargs):
        with stage("planner"):
            return await plan(self, *args, **kwargs)

    with (
        patch.object(IntentClassifier, "classify", observe_intent),
        patch.object(Planner, method, observe_plan),
    ):
        yield


async def prepare(env, fixture):
    if not fixture:
        return
    if fixture not in {"unpaid_tee", "payment_record_missing"}:
        raise RunStopped(f"Unsupported frozen business fixture: {fixture}")
    async with env.container.session_factory() as db:
        order = await db.get(OrderRow, "ORD10003")
        if fixture == "unpaid_tee":
            order.status = "created"
        order.paid_at = None
        await db.commit()


def skill_observation(state, spans):
    hints = [hint.name for hint in getattr(state.get("intent"), "skill_hints", ())]
    selection = state.get("skill_selection")
    selected = selection.name if selection is not None else None
    eligible = getattr(selection, "eligible", None)
    if eligible is None:
        eligible = [selected] if selected and not selection.clarification else []

    def events(name):
        return [record["metadata"] for record in spans if record["name"] == name]

    return {
        "hints": sorted(set(hints)),
        "relevant": list(getattr(selection, "relevant", hints)),
        "eligible": list(eligible),
        "selected": [selected] if selected else [],
        "activated": sorted(
            {item["skill_name"] for item in events("skill.activation") if "skill_name" in item}
        ),
        "reason": getattr(selection, "reason_code", None),
        "instructions": events("skill.instructions"),
        "resources": events("skill.resource"),
        "workflow": [
            item["metadata"] for item in spans if item["name"].startswith("skill.workflow")
        ],
    }


def raw_plan(row, registry):
    """Keep model output distinct from the sanitized AgentPlan and the executed tools."""
    choice = row["response"]["choices"][0]
    choice_json = choice["message"].get("content") or ""
    if choice.get("finish_reason") == "length":
        return {"request_id": row["id"], "decoded": None, "schema_error": "truncated"}
    decoded, error = None, None
    try:
        parsed = extract_json_object(choice_json)
        decoded = AgentPlan.model_validate(parsed).model_dump(mode="json")
        for step in decoded["steps"]:
            if step["tool_name"]:
                registry.get(step["tool_name"]).parse(step["arguments"])
    except (ValueError, AppError, LLMOutputError):
        error = "plan_or_arguments"
    return {"request_id": row["id"], "decoded": decoded, "schema_error": error}


def strategy_name(plan, initial, state):
    if plan:
        if state.get("confirmed_action"):
            return "confirmed"
        if plan.get("read_contract_mode") in {"partial", "clarify"}:
            return plan["read_contract_mode"]
        return plan.get("planning_strategy", "dynamic")
    context = state.get("selected_context") or initial.get("selected_context")
    if getattr(context, "needs_clarification", False):
        return "clarify"
    return "none"


async def execute(case, oracle, arm, repeat, llm, ledger):
    trace, observed = [], []
    recorder = TraceRecorder(enabled=True, sink=trace.extend)
    case_start = time.perf_counter()
    with observe_graph():
        env = BusinessEnvironment(llm=llm, tracer=recorder, memory_mode="M2")
        with patch("app.services.seed.utcnow", return_value=CLOCK):
            await env.__aenter__()
        try:
            await prepare(env, oracle.get("fixture"))
            initial = await env.snapshot()
            graph_state, entry_state = {}, {}
            original_invoke, original_initial = env.service._invoke, env.service._initial_state

            async def collect_graph(*args, **kwargs):
                value = await original_invoke(*args, **kwargs)
                graph_state.update(value)
                return value

            async def collect_entry(*args, **kwargs):
                value = await original_initial(*args, **kwargs)
                entry_state.update(value)
                return value

            with (
                patch.object(env.service, "_invoke", collect_graph),
                patch.object(env.service, "_initial_state", collect_entry),
            ):
                session, pending = None, None
                for index, turn in enumerate(case.turns, 1):
                    graph_state.clear()
                    entry_state.clear()
                    trace.clear()
                    if turn.state_changes:
                        await env.change_order_states(turn.state_changes)
                    if oracle.get("expire_turn") == index and pending:
                        item = env.service._pending_actions[pending]
                        env.service._pending_actions[pending] = replace(item, expires_at=0)
                    before_turn = await env.snapshot()
                    job = f"{arm}/{case.id}/{repeat}/{index}"
                    action = "not-issued" if turn.invalid_confirmation else None
                    if turn.confirm:
                        action = pending or "not-issued"
                    request = ChatRequest(
                        message=turn.message,
                        user_id=turn.user_id or case.user_id,
                        session_id=None if turn.new_session else session,
                        confirm_action_id=action,
                    )
                    started = time.perf_counter()
                    response = error = None
                    token = REQUEST_SCOPE.set({"job": job, "stage": "graph"})
                    try:
                        with capture_tools() as calls:
                            try:
                                response = await env.service.chat(request, trace_id=job)
                            except AppError as exc:
                                error = exc.error_code.value
                    finally:
                        REQUEST_SCOPE.reset(token)
                    duration = (time.perf_counter() - started) * 1000
                    if response:
                        session = response.session_id
                        if response.pending_action:
                            pending = response.pending_action.action_id
                    receipts = [row for row in ledger.requests() if row["scope"]["job"] == job]
                    spans = [
                        {
                            "name": event.name,
                            "metadata": event.metadata,
                            "status": event.status,
                            "latency_ms": event.latency_ms,
                        }
                        for event in trace
                    ]
                    committed = await env.snapshot()
                    plan = serial(graph_state.get("plan"))
                    goals = serial(graph_state.get("task_goals") or [])
                    observed.append(
                        {
                            "index": index,
                            "request": serial(request),
                            "context": serial(
                                graph_state.get("selected_context")
                                or entry_state.get("selected_context")
                            ),
                            "intent": serial(graph_state.get("intent")) or {},
                            "goals": goals,
                            "verified_dependencies": [
                                {
                                    "predicate": "is_paid",
                                    "entity_id": goal["verified_dependency"][
                                        "prerequisite_order_id"
                                    ],
                                    "target": [goal["kind"], goal.get("entity_id")],
                                }
                                for goal in goals
                                if goal.get("verified_dependency")
                            ],
                            "skills": skill_observation(graph_state, spans),
                            "strategy": strategy_name(plan, entry_state, graph_state),
                            "route": serial(graph_state.get("strategy")),
                            "plan": plan,
                            "confirmed_action": serial(entry_state.get("confirmed_action")),
                            "tool_events": [{**event, "turn": index} for event in calls],
                            "evidence": serial(graph_state.get("tool_results") or []),
                            "tool_result_steps": serial(graph_state.get("tool_result_steps") or []),
                            "state_unchanged": before_turn == committed,
                            "response": serial(response),
                            "error": error or graph_state.get("error"),
                            "spans": spans,
                            "latency_ms": duration,
                            "request_ids": [row["id"] for row in receipts],
                            "raw_planner": [
                                raw_plan(row, env.service.registry)
                                for row in receipts
                                if row["scope"]["stage"] == "planner"
                            ],
                        }
                    )
            after = await env.snapshot()
        finally:
            await env.__aexit__()
    result = {
        "case": case.id,
        "arm": arm,
        "repeat": repeat,
        "cohort": oracle["cohort"],
        "turns": observed,
        "before": initial,
        "after": after,
        "latency_ms": (time.perf_counter() - case_start) * 1000,
    }
    result["scores"] = score_case(case, oracle, result)
    return result


def tariff(row):
    local = datetime.fromisoformat(row["admitted"]).astimezone(TAIPEI)
    peak = local.weekday() < 5 and (9 <= local.hour < 12 or 14 <= local.hour < 18)
    total = row["actual"] or 0
    return total if peak else total // 2


def summary(cases, oracles, rows, receipts, totals):
    receipt_map = {row["id"]: row for row in receipts}
    runs = {arm: [row for row in rows if row["arm"] == arm and row["repeat"] == 1] for arm in ARMS}
    groups = {}
    for arm, run in runs.items():
        groups[arm] = {"all": metric_group(run, receipt_map)}
        for cohort in ("basic", "historical", "holdout", "safety"):
            groups[arm][cohort] = metric_group(
                [row for row in run if row["cohort"] == cohort], receipt_map
            )
    matched_cases = set.intersection(*(set(row["case"] for row in run) for run in runs.values()))
    subsets = {}
    for strategy in ("direct", "skill", "dynamic"):
        subset = {
            key
            for key in matched_cases
            if any(strategy in gold.get("strategy", []) for gold in oracles[key]["turns"].values())
        }
        subsets[strategy] = {
            "cases": sorted(subset),
            "groups": {
                arm: metric_group([row for row in run if row["case"] in subset], receipt_map)
                for arm, run in runs.items()
            },
        }
    indices = {(row["arm"], row["case"], row["repeat"]): row for row in rows}
    repeats = {}
    planned_repeats = set()
    for arm in REPEAT_ARMS:
        for case_id in scheduled(cases, oracles, arm, None, True):
            planned_repeats.add((arm, case_id, 2))
            first, second = indices.get((arm, case_id, 1)), indices.get((arm, case_id, 2))
            if first is not None and second is not None:
                repeats.setdefault(case_id, {})[arm] = [
                    first["scores"]["success"],
                    second["scores"]["success"],
                ]
    total = sum(row["tariff_nano_cny"] for row in receipts)
    linked = {key for row in rows for turn in row["turns"] for key in turn["request_ids"]}
    return {
        "ledger": totals,
        "tariff_cost_cny": cny(total),
        "models": dict(
            Counter(row["response"].get("model", "unknown") for row in receipts if row["response"])
        ),
        "model_fingerprints": dict(
            Counter(
                row["response"].get("system_fingerprint") or "unknown"
                for row in receipts
                if row["response"]
            )
        ),
        "paired_primary_cases": sorted(matched_cases),
        "primary_complete": len(matched_cases) == len(cases),
        "repeats_complete": planned_repeats <= indices.keys(),
        "repeated": repeats,
        "groups": groups,
        "matched_strategy_subsets": subsets,
        "unlinked_receipts": sorted(receipt_map.keys() - linked),
    }


def collect(output, ledger, cases, oracles):
    receipts = ledger.requests()
    for row in receipts:
        row["tariff_nano_cny"] = tariff(row)
    rows = [row for arm in ARMS for row in read_rows(output / f"{arm}.jsonl")]
    save(output / "requests.json", receipts)
    save(output / "summary.json", summary(cases, oracles, rows, receipts, ledger.totals()))


def verify_evidence(output, cases, oracles):
    receipts = read_report(output / "requests.json")
    report = read_report(output / "summary.json")
    rows = [row for arm in ARMS for row in read_rows(output / f"{arm}.jsonl")]
    if len({(row["arm"], row["case"], row["repeat"]) for row in rows}) != len(rows):
        raise RunStopped("Duplicate recorded case run")
    receipt_index = {receipt["id"]: receipt for receipt in receipts}
    if len(receipt_index) != len(receipts):
        raise RunStopped("Duplicate saved HTTP receipt")
    manifests = [read_report(path) for path in sorted(output.glob("*_manifest.json"))]
    allowed = set()
    source_inputs = {}
    for manifest in manifests:
        arm, ordinal = manifest["arm"], manifest["repeat"]
        intended = scheduled(cases, oracles, arm, manifest["block"], ordinal == 2)
        source = manifest["source_commit"]
        harness = manifest["harness_commit"]
        if harness not in source_inputs:
            source_inputs[harness] = verify_harness(harness)
        if (
            manifest["cases"] != intended
            or source != PINNED.get(arm, harness)
            or manifest["fixtures_sha256"] != FROZEN_FIXTURE_SHA
            or manifest["evaluation_inputs"] != source_inputs[harness]
            or not manifest["source_files"]
        ):
            raise RunStopped(f"Frozen run identity changed for {arm} block {manifest['block']}")
        allowed.update((arm, case, ordinal) for case in intended)
    linked = set()
    for row in rows:
        case_id = row["case"]
        arm, repeat = row["arm"], row["repeat"]
        if (arm, case_id, repeat) not in allowed:
            raise RunStopped(f"Observed case is missing its arm manifest: {case_id}")
        if row["scores"] != score_case(cases[case_id], oracles[case_id], row):
            raise RunStopped(f"Frozen scoring recomputation differs in {case_id}")
        for turn in row["turns"]:
            expected_job = f"{arm}/{case_id}/{repeat}/{turn['index']}"
            used = turn["request_ids"]
            if any(
                key in linked or receipt_index[key]["scope"]["job"] != expected_job for key in used
            ):
                raise RunStopped(f"HTTP receipt linked to the wrong case turn: {expected_job}")
            if [item["request_id"] for item in turn["raw_planner"]] != [
                key for key in used if receipt_index[key]["scope"]["stage"] == "planner"
            ]:
                raise RunStopped(
                    f"Raw planning not linked to its complete HTTP set: {expected_job}"
                )
            linked.update(used)
    for receipt in receipts:
        usage = metered_usage(receipt["response"])
        if not usage or usage != receipt["usage"] or receipt["http_status"] != 200:
            raise RunStopped(f"Unverifiable HTTP receipt {receipt['id']}")
        actual = (
            usage["prompt_cache_hit_tokens"] * RATE["cache_hit"]
            + usage["prompt_cache_miss_tokens"] * RATE["cache_miss"]
            + usage["completion_tokens"] * RATE["completion"]
        )
        if receipt["actual"] != actual or receipt["tariff_nano_cny"] != tariff(receipt):
            raise RunStopped(f"Tariff drift for HTTP receipt {receipt['id']}")
        if (
            receipt["request"]["thinking"] != {"type": "disabled"}
            or receipt["request"]["model"] != MODEL
        ):
            raise RunStopped(f"Unpinned model or inference mode at receipt {receipt['id']}")
    totals = report["ledger"]
    if totals["attempts"] != len(receipts) or totals["actual_cost_cny"] != cny(
        sum(row["actual"] for row in receipts)
    ):
        raise RunStopped("Shared budget totals differ from saved HTTP receipts")
    if report != summary(cases, oracles, rows, receipts, totals):
        raise RunStopped("Recomputed joint metrics differ from report")
    print(
        json.dumps(
            {
                "verified": True,
                "requests": len(receipts),
                "case_runs": len(rows),
                "cost_cny": report["tariff_cost_cny"],
                "primary_complete": report["primary_complete"],
            }
        )
    )


def release_manifest(options, cases, oracles, input_digest):
    check_commit(options.source_commit)
    check_commit(options.harness_commit)
    expected_source = PINNED.get(options.arm, options.harness_commit)
    if options.source_commit != expected_source:
        raise RunStopped("Execution archive does not match the frozen P5 comparison")
    return {
        "schema": "p5_live_joint_v1",
        "arm": options.arm,
        "block": options.block,
        "repeat": 2 if options.repeat else 1,
        "source_commit": options.source_commit,
        "harness_commit": options.harness_commit,
        "source_files": verify_source(options.source_commit),
        "evaluation_inputs": verify_harness(options.harness_commit),
        "cases": scheduled(cases, oracles, options.arm, options.block, options.repeat),
        "fixtures_sha256": input_digest,
        "seed_time": CLOCK.isoformat(),
        "memory_mode": "M2",
        "provider_origin": f"https://{HOST}",
        "model": MODEL,
        "thinking": "disabled",
        "max_attempts": 1,
        "planner_mode": "json",
        "strict": False,
        "cap_cny": options.cap_cny,
        "http_cap": options.max_requests,
        "runtime_dependencies": {
            name: metadata.version(name)
            for name in ("httpx", "langgraph", "pydantic", "sqlalchemy")
        },
    }


async def run(options):
    cases, oracles, input_digest = fixtures()
    if options.verify:
        verify_evidence(options.output, cases, oracles)
        return
    if options.arm:
        manifest = release_manifest(options, cases, oracles, input_digest)
        if options.dry_run:
            print(
                json.dumps(
                    {**manifest, "source_files": len(manifest["source_files"])},
                    ensure_ascii=True,
                    indent=2,
                )
            )
            return
    options.output.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(
        options.output / "ledger.sqlite3",
        cap_cny=options.cap_cny,
        max_requests=options.max_requests,
    )
    if options.collect:
        collect(options.output, ledger, cases, oracles)
        return
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RunStopped("Live replay requires the existing DeepSeek credential")
    tag = options.arm + (
        "_repeat"
        if options.repeat
        else f"_block{options.block}"
        if options.block is not None
        else ""
    )
    manifest_file = options.output / f"{tag}_manifest.json"
    if manifest_file.exists():
        if read_report(manifest_file) != manifest:
            raise RunStopped("Existing arm manifest does not match frozen resume inputs")
    else:
        save(manifest_file, manifest)
    case_file = options.output / f"{options.arm}.jsonl"
    repeat = manifest["repeat"]
    completed = {row["case"] for row in read_rows(case_file) if row["repeat"] == repeat}
    started = {
        key
        for row in ledger.requests()
        for arm, key, ordinal, _ in [row["scope"]["job"].split("/")]
        if arm == options.arm and int(ordinal) == repeat
    }
    if interrupted := started - completed:
        print(f"Do not rebill incomplete cases: {', '.join(sorted(interrupted))}", flush=True)
    settings = Settings(
        _env_file=None,
        deepseek_api_key=key,
        deepseek_model=MODEL,
        deepseek_base_url=f"https://{HOST}",
        llm_max_retries=1,
        token_budget=128_000,
    )
    async with httpx.AsyncClient(
        base_url=f"https://{HOST}",
        transport=ComparingTransport(ledger),
        trust_env=False,
        timeout=40.0,
    ) as client:
        llm = DeepSeekProvider(settings, client=client)
        for case_id in manifest["cases"]:
            if case_id not in completed | started:
                row = await execute(
                    cases[case_id], oracles[case_id], options.arm, repeat, llm, ledger
                )
                append_jsonl(case_file, row)
                print(
                    f"{options.arm}/{repeat} {case_id} pass={row['scores']['success']}", flush=True
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--arm", choices=ARMS)
    operation.add_argument("--collect", action="store_true")
    operation.add_argument("--verify", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--harness-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--block", type=int, choices=(0, 1))
    parser.add_argument("--repeat", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cap-cny", default="3.20")
    parser.add_argument("--max-requests", default=260, type=int)
    options = parser.parse_args()
    if options.repeat and (options.arm not in REPEAT_ARMS or options.block is not None):
        parser.error("The two frozen cases repeat only after primary arms D and E")
    if not options.dry_run and not options.output:
        parser.error("An output path is required")
    if not 0 < Decimal(options.cap_cny) <= MAX_CNY or not 0 < options.max_requests <= MAX_REQUESTS:
        parser.error("The combined evaluation cannot exceed ¥3.20 and 260 attempts")
    isolated = {
        name: value
        for name, value in os.environ.items()
        if name.lower() not in Settings.model_fields or name.lower() == "deepseek_api_key"
    }
    isolated.update(LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
    with patch.dict(os.environ, isolated, clear=True):
        asyncio.run(run(options))


if __name__ == "__main__":
    main()
