"""Explicit single-stage launcher. Never retry STARTED/consumed paid tasks."""

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import OrderRow, ProductRow
from research.docs.agent_engineering_upgrade.p4_dependency_integration.live_api import (
    assert_confirmation_effects,
    snapshot,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    free_port,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

from .common import HERE, ROOT, RUN, verify_freeze
from .meter import Ledger, SafetyStop, read, stamp, write
from .score import score


def normalized(cfg):
    data = asyncio.run(snapshot(cfg))
    return {
        name: sorted(
            json.loads(json.dumps(rows, default=str)), key=lambda r: json.dumps(r, sort_keys=True)
        )
        for name, rows in data.items()
    }


async def seed(cfg, cases):
    engine = create_async_engine(cfg["database_url"])
    try:
        async with async_sessionmaker(engine)() as db:
            for c in cases:
                if c.get("order") and await db.get(OrderRow, c["order"]) is None:
                    db.add(
                        OrderRow(
                            order_id=c["order"],
                            user_id="u_demo",
                            status=c["status"],
                            total_cents=c["cents"],
                            tracking_no=c["tracking"],
                        )
                    )
            if await db.get(ProductRow, "SKU-P4C-ASTER") is None:
                db.add(
                    ProductRow(
                        sku="SKU-P4C-ASTER",
                        name="合成星屿样品",
                        category="评测",
                        price_cents=1450,
                        inventory=17,
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()


class Api:
    def __init__(self, label, cfg):
        self.label, self.cfg = label, cfg
        self.directory = RUN / ("worker_" + label)
        if self.directory.exists():
            raise SafetyStop(
                "stage worker already exists; inspect durable state, no automatic paid replay"
            )
        self.port, self.token = free_port(), secrets.token_hex(24)
        self.url = f"http://127.0.0.1:{self.port}"
        self.out = (RUN / (label + "_stdout.log")).open("wb")
        self.err = (RUN / (label + "_stderr.log")).open("wb")
        env = os.environ.copy()
        for name in list(env):
            if name.lower().endswith("_proxy"):
                env.pop(name)
        env.update(
            P4C_CONTROL_TOKEN=self.token,
            LANGCHAIN_TRACING_V2="false",
            LANGSMITH_TRACING="false",
            EXPERIENCE_MEMORY_MODE="off",
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                __package__ + ".worker",
                "--port",
                str(self.port),
                "--label",
                label,
            ],
            cwd=ROOT,
            env=env,
            stdout=self.out,
            stderr=self.err,
        )
        self.client = httpx.Client(timeout=180, trust_env=False)

    def wait(self):
        for _ in range(400):
            if self.process.poll() is not None:
                raise RuntimeError("worker startup failed;inspect private local logs")
            try:
                if (
                    self.client.get(self.url + "/api/v1/health").status_code == 200
                    and (self.directory / "startup.json").exists()
                ):
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise TimeoutError("startup bounded40s")

    def stop(self):
        if self.process.poll() is None:
            try:
                self.client.post(self.url + "/__p4c_stop", headers={"x-p4-control": self.token})
                self.process.wait(timeout=15)
            except (httpx.HTTPError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        write(
            RUN / (self.label + "_owned_cleanup.json"),
            dict(pid=self.process.pid, exit_code=self.process.returncode),
        )
        self.client.close()
        self.out.close()
        self.err.close()

    def request(self, case, payload, protocol="json"):
        trace = "p4c_" + uuid.uuid4().hex
        row = dict(
            case=case,
            before=normalized(self.cfg),
            payload=payload,
            trace_id=trace,
            tools=[],
            events=[],
        )
        started = time.perf_counter()
        try:
            r = self.client.post(
                self.url + "/api/v1/chat" + ("/stream" if protocol == "sse" else ""),
                json=payload,
                headers={
                    "authorization": "Bearer " + TOKENS["user"],
                    "x-p4-case": case,
                    "x-trace-id": trace,
                },
            )
            row.update(status=r.status_code, text=r.text)
            if protocol == "sse":
                events = [
                    json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")
                ]
                answers = [e["data"] for e in events if e["event"] == "answer"]
                row["body"] = answers[-1] if answers else {}
                row["protocol_valid"] = bool(
                    events
                    and events[0]["event"] == "started"
                    and events[-1]["event"] == "done"
                    and len(answers) == 1
                    and not any(e["event"] == "error" for e in events)
                    and "".join(e.get("text", "") for e in events if e["event"] == "token")
                    == row["body"].get("answer")
                )
            else:
                row["body"] = r.json()
                row["protocol_valid"] = True
        except BaseException as exc:
            row.update(
                transport_error=type(exc).__name__, status=None, protocol_valid=False, body={}
            )
        finally:
            row.update(
                latency_ms=(time.perf_counter() - started) * 1000, after=normalized(self.cfg)
            )
            path = self.directory / "events.jsonl"
            if path.exists():
                row["events"] = [
                    e
                    for e in [json.loads(line) for line in path.read_text().splitlines()]
                    if e.get("trace_id") == trace
                ]
                # Trace batches use the root trace_id through captured tools; spans are kept raw below.
                all_events = [json.loads(line) for line in path.read_text().splitlines()]
                row["spans"] = [
                    s for e in all_events if e.get("case") == case for s in e.get("spans", [])
                ]
                row["tools"] = [t for e in row["events"] for t in e.get("calls", [])]
            write(RUN / ("request_" + trace + ".json"), row)
        return row


def task(api, case):
    path = RUN / ("task_" + case["id"] + ".json")
    if path.exists():
        raise SafetyStop("task consumed/uncertain;never repeat paid task")
    write(path, dict(status="STARTED", case=case, started_at=stamp()))
    rows = []
    try:
        first = api.request(case["id"], dict(message=case["message"]), case["protocol"])
        rows.append(first)
        result = dict(first)
        if case.get("confirm") and (first.get("body") or {}).get("pending_action"):
            action = first["body"]["pending_action"]
            payload = dict(
                message="确认取消",
                session_id=first["body"]["session_id"],
                confirm_action_id=action["action_id"],
                idempotency_key="p4c_" + case["id"],
            )
            confirmed = api.request(case["id"], payload)
            rows.append(confirmed)
            repeated = api.request(case["id"], payload)
            rows.append(repeated)
            result.update(
                body=confirmed["body"],
                after=repeated["after"],
                tools=[t for r in rows for t in r["tools"]],
            )
            try:
                assert all(r["status"] == 200 for r in rows)
                assert confirmed["after"]["orders"] == repeated["after"]["orders"]
                assert confirmed["after"]["audit_logs"] == repeated["after"]["audit_logs"]
                assert_confirmation_effects(
                    first["before"],
                    repeated["after"],
                    case["order"],
                    action["action_id"],
                    {r["trace_id"] for r in rows},
                )
                result["confirmation_verified"] = True
            except (AssertionError, KeyError):
                result["confirmation_verified"] = False
        result["latency_ms"] = sum(r["latency_ms"] for r in rows)
        verdict = score(case, result)
        write(
            path,
            dict(
                status="COMPLETED",
                case=case,
                result=result,
                score=verdict,
                requests=[r["trace_id"] for r in rows],
            ),
        )
        return verdict
    except BaseException as exc:
        write(
            path,
            dict(
                status="INTERRUPTED", case=case, error=type(exc).__name__, captured_http=len(rows)
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["health", "pilot", "test"])
    args = parser.parse_args()
    frozen = verify_freeze()
    RUN.mkdir(exist_ok=True, parents=True)
    manifest, cfg = live_config()
    command(manifest, "ps")
    cases = read(HERE / "datasets.json")["cases"]
    if args.stage == "test":
        for case in cases[:2]:
            p = RUN / ("task_" + case["id"] + ".json")
            if not p.exists() or read(p).get("status") != "COMPLETED":
                raise SafetyStop("pilot incomplete;no independent dispatch")
    asyncio.run(seed(cfg, cases))
    api = Api(args.stage, cfg)
    try:
        api.wait()
        if args.stage == "health":
            write(
                RUN / "free_health.json",
                dict(
                    ready=api.client.get(api.url + "/api/v1/ready").json(),
                    paid_requests=0,
                    freeze_sha=frozen["base"],
                ),
            )
        else:
            selected = cases[:2] if args.stage == "pilot" else cases[2:]
            for case in selected:
                print(case["id"], json.dumps(task(api, case), ensure_ascii=False), flush=True)
                ledger = Ledger(RUN)
                if any(r.get("error") or r["status"] != "RESPONSE" for r in ledger.rows):
                    raise SafetyStop("unsafe ledger;end stage")
    finally:
        api.stop()
    write(
        RUN / (args.stage + "_summary.json"),
        dict(totals=Ledger(RUN).totals(), stage=args.stage, finished=stamp()),
    )


if __name__ == "__main__":
    main()
