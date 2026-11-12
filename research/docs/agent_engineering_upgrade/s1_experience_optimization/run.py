"""One pass per frozen case/arm; no automatic replay of consumed paid work."""

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import sys
import time

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import MessageRow, OrderItemRow, OrderRow, RefundRow
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    free_port,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS
from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.run import normalized

from .common import HERE, ROOT, RUN, read, save, sha, verify_freeze
from .meter import Ledger, SafetyStop, write
from .scoring import score


def business(snapshot):
    return {k: v for k, v in snapshot.items() if k not in {"sessions", "messages"}}


async def validate_existing(db, existing, item):
    from datetime import datetime

    values = {k: v for k, v in item.items() if k not in {"items", "refunds"}}
    values["user_id"] = "s1ex_probe_user"
    for name in ["created_at", "paid_at", "shipped_at", "delivered_at"]:
        if values.get(name):
            values[name] = datetime.fromisoformat(values[name])
    if any(getattr(existing, k) != v for k, v in values.items()):
        raise SafetyStop("existing synthetic order does not match frozen fixture; no overwrite")
    items = (
        await db.scalars(select(OrderItemRow).where(OrderItemRow.order_id == item["order_id"]))
    ).all()
    actual_items = [
        {k: getattr(row, k) for k in ["sku", "name", "quantity", "unit_price_cents", "customized"]}
        for row in items
    ]
    refunds = (
        await db.scalars(select(RefundRow).where(RefundRow.order_id == item["order_id"]))
    ).all()
    actual_refunds = [
        {k: getattr(row, k) for k in ["refund_id", "status", "amount_cents"]} for row in refunds
    ]

    def ordered(rows):
        return sorted(rows, key=lambda x: json.dumps(x, sort_keys=True))

    if ordered(actual_items) != ordered(item["items"]) or ordered(actual_refunds) != ordered(
        item["refunds"]
    ):
        raise SafetyStop(
            "existing synthetic details/refunds conflict with frozen fixture; no overwrite"
        )


async def preflight_eligibility(task):
    from app.experience.contracts import EvidenceRef
    from app.experience.isolated import select_isolated
    from app.experience.shadow import EvidenceResolver
    from app.experience.storage import ExperienceRepository
    from app.tools.factory import build_tool_registry

    from .common import STATE, scope_for

    engine = create_async_engine("sqlite+aiosqlite:///" + str(HERE / ".private/experience.sqlite3"))
    try:
        repo = ExperienceRepository(
            async_sessionmaker(engine, expire_on_commit=False), resolver=EvidenceResolver(STATE)
        )
        permits = {k: EvidenceRef.model_validate(v) for k, v in read(HERE / "permits.json").items()}
        selected = await select_isolated(
            repo,
            scope_for(task["sessions"]["E2"]),
            task["query"],
            build_tool_registry(object()),
            permits,
            resolver=EvidenceResolver(STATE),
            isolated=True,
        )
        if not selected:
            raise SafetyStop("no qualified E2 for frozen task; don't start triplet")
        return {
            "case": task["id"],
            "eligible_count": len(selected),
            "families": [c.family for c in selected],
        }
    finally:
        await engine.dispose()


async def seed(cfg):
    from datetime import datetime

    engine = create_async_engine(cfg["database_url"])
    try:
        async with async_sessionmaker(engine)() as db:
            for task in read(HERE / "tasks.json")["tasks"]:
                for item in task["orders"]:
                    existing = await db.get(OrderRow, item["order_id"])
                    if existing is not None:
                        await validate_existing(db, existing, item)
                        continue
                    values = {k: v for k, v in item.items() if k not in ["items", "refunds"]}
                    for name in ["created_at", "paid_at", "shipped_at", "delivered_at"]:
                        if values.get(name):
                            values[name] = datetime.fromisoformat(values[name])
                    db.add(OrderRow(**values, user_id="s1ex_probe_user"))
                    await db.flush()
                    for line in item["items"]:
                        db.add(OrderItemRow(order_id=item["order_id"], **line))
                    for row in item["refunds"]:
                        db.add(
                            RefundRow(
                                order_id=item["order_id"], reason="synthetic existing record", **row
                            )
                        )
            await db.commit()
    finally:
        await engine.dispose()


async def empty_session(cfg, session):
    engine = create_async_engine(cfg["database_url"])
    try:
        async with engine.connect() as conn:
            assert not (
                await conn.execute(select(MessageRow).where(MessageRow.session_id == session))
            ).all()
    finally:
        await engine.dispose()


class Api:
    def __init__(self, stage):
        self.stage = stage
        self.port = free_port()
        self.token = secrets.token_hex(24)
        self.url = f"http://127.0.0.1:{self.port}"
        self.directory = RUN / ("worker_" + stage)
        self.out = (RUN / f"{stage}_stdout.log").open("xb")
        self.err = (RUN / f"{stage}_stderr.log").open("xb")
        env = os.environ.copy()
        for k in list(env):
            if k.lower().endswith("_proxy"):
                env.pop(k)
        env.update(
            EX_CONTROL_TOKEN=self.token,
            EXPERIENCE_MEMORY_MODE="off",
            LANGSMITH_TRACING="false",
            LANGCHAIN_TRACING_V2="false",
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "research.docs.agent_engineering_upgrade.s1_experience_optimization.worker",
                "--stage",
                stage,
                "--port",
                str(self.port),
            ],
            cwd=ROOT,
            env=env,
            stdout=self.out,
            stderr=self.err,
        )
        self.client = httpx.Client(timeout=180, trust_env=False)

    def wait(self):
        for _ in range(600):
            if self.process.poll() is not None:
                raise RuntimeError("EX worker startup failed;inspect retained private log")
            try:
                if (
                    self.client.get(self.url + "/api/v1/health").status_code == 200
                    and (self.directory / "startup.json").exists()
                ):
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise TimeoutError("EX startup60s")

    def stop(self):
        if self.process.poll() is None:
            try:
                self.client.post(self.url + "/__ex_stop", headers={"x-ex-control": self.token})
                self.process.wait(timeout=15)
            except (httpx.HTTPError, subprocess.TimeoutExpired):
                self.process.terminate()
                self.process.wait(timeout=10)
        save(
            RUN / (self.stage + "_owned_cleanup.json"),
            {"pid": self.process.pid, "exit_code": self.process.returncode},
        )
        self.client.close()
        self.out.close()
        self.err.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["development", "independent"])
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    verify_freeze()
    if args.stage == "independent":
        review = read(HERE / "evidence/development_review.json")
        if (
            review.get("freeze_sha256") != sha(HERE / "freeze.json")
            or review.get("allow_independent") is not True
        ):
            raise SafetyStop("durable reviewed-development gate required")
    marker = RUN / (args.stage + "_STARTED.json")
    if marker.exists():
        raise SafetyStop("consumed stage;inspect checkpoint,never replay paid tasks")
    write(
        marker,
        {"stage": args.stage, "status": "STARTED", "freeze_sha256": sha(HERE / "freeze.json")},
    )
    manifest, cfg = live_config()
    command(manifest, "ps")
    asyncio.run(seed(cfg))
    eligible = [
        asyncio.run(preflight_eligibility(t))
        for t in read(HERE / "tasks.json")["tasks"]
        if t["split"] == args.stage
    ]
    write(RUN / (args.stage + "_eligibility.json"), eligible)
    api = Api(args.stage)
    try:
        api.wait()
        first_task = next(t for t in read(HERE / "public_tasks.json") if t["split"] == args.stage)
        probes = []
        for kind, authorization, control_value in [
            ("other_authenticated_subject", TOKENS["other"], api.token),
            ("missing_control", TOKENS["user"], ""),
        ]:
            before_requests = len(Ledger(RUN).rows)
            denied = api.client.post(
                api.url + "/api/v1/chat",
                json={"message": first_task["query"], "session_id": first_task["sessions"]["E2"]},
                headers={
                    "authorization": "Bearer " + authorization,
                    "x-ex-control": control_value,
                    "x-ex-case": first_task["id"],
                    "x-ex-arm": "E2",
                },
            )
            assert denied.status_code == 403 and len(Ledger(RUN).rows) == before_requests
            probes.append({"probe": kind, "status": denied.status_code, "paid_requests_added": 0})
        write(RUN / (args.stage + "_free_auth_probes.json"), probes)
        for task in read(HERE / "tasks.json")["tasks"]:
            if task["split"] != args.stage:
                continue
            ledger = Ledger(RUN)
            ledger.admit_triplet()
            results = []
            order = ["E0", "E1", "E2"] if args.stage == "development" else ["E2", "E1", "E0"]
            for arm in order:
                session = task["sessions"][arm]
                asyncio.run(empty_session(cfg, session))
                before = normalized(cfg)
                group = task["id"] + "_" + arm
                write(
                    RUN / (group + "_STARTED.json"),
                    {"status": "STARTED", "case": task["id"], "arm": arm},
                )
                started = time.perf_counter()
                response = api.client.post(
                    api.url + "/api/v1/chat",
                    json={"message": task["query"], "session_id": session},
                    headers={
                        "authorization": "Bearer " + TOKENS["user"],
                        "x-ex-control": api.token,
                        "x-ex-case": task["id"],
                        "x-ex-arm": arm,
                    },
                )
                latency = (time.perf_counter() - started) * 1000
                after = normalized(cfg)
                path = RUN / (group + ".json")
                body = response.json()
                events = [
                    json.loads(x)
                    for x in (api.directory / "events.jsonl").read_text().splitlines()
                    if x
                ]
                events = [
                    e
                    for e in events
                    if e.get("case") == group or e.get("trace_id") == body.get("trace_id")
                ]
                tools = [t for e in events if e.get("kind") == "tools" for t in e["calls"]]
                ledger = Ledger(RUN)
                rows = [r for r in ledger.rows if r["group"] == group]
                capture = {
                    "case": task["id"],
                    "split": task["split"],
                    "arm": arm,
                    "query": task["query"],
                    "session": session,
                    "status": response.status_code,
                    "body": body,
                    "tools": tools,
                    "events": events,
                    "business_before": business(before),
                    "business_after": business(after),
                    "initial_session_empty": True,
                    "latency_ms": latency,
                    "model_requests": len(rows),
                    "tokens": sum(r["usage"]["total_tokens"] for r in rows if r.get("usage")),
                    "freeze_sha256": sha(HERE / "freeze.json"),
                }
                capture["scores"] = score(task, body, tools, business(before) == business(after))
                write(path, capture)
                if response.status_code != 200:
                    raise SafetyStop("HTTPfailure;originalevidencepreserved/no retry")
                ledger.safe()
                results.append(capture)
                print(
                    json.dumps(
                        {
                            "case": task["id"],
                            "arm": arm,
                            "requests": len(rows),
                            "execution": capture["scores"]["execution_success_proxy"],
                            "bounded": capture["scores"]["bounded_e2e_proxy"],
                            "global": ledger.totals(),
                        }
                    ),
                    flush=True,
                )
            assert len(results) == 3
            exposed = any(
                e.get("kind") == "experience_planner" and e.get("injected", 0) > 0
                for r in results
                if r["arm"] == "E2"
                for e in r["events"]
            )
            if not exposed:
                write(
                    RUN / (task["id"] + "_NOT_EXPOSED.json"),
                    {
                        "case": task["id"],
                        "all_http_responses_saved": True,
                        "effect_eligible": False,
                        "reason": "NO_ACTUAL_E2_PLANNER_INJECTION",
                    },
                )
                continue  # No fake E2/no-effect control may enter benefit denominators.
            assert all(
                r["query"] == results[0]["query"]
                and r["business_before"] == results[0]["business_before"]
                for r in results
            )
            write(
                RUN / (task["id"] + "_TRIPLET_COMPLETE.json"),
                {
                    "case": task["id"],
                    "complete": True,
                    "same_query_business": True,
                    "arms": [r["arm"] for r in results],
                },
            )
    finally:
        api.stop()


if __name__ == "__main__":
    main()
