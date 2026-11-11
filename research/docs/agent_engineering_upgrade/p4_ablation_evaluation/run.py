"""Consume new baseline or complete paired tasks once. No paid replay/retry."""

import argparse
import asyncio
import json

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import MessageRow, OrderRow, SessionRow
from research.docs.agent_engineering_upgrade.p4_dependency_integration.live_api import (
    assert_confirmation_effects,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import exclusive, stamp

from .api import Api
from .common import HERE, RUN, verify_freeze
from .meter import Ledger, SafetyStop, write
from .scoring import score, unchanged


async def seed(cfg):
    engine = create_async_engine(cfg["database_url"])
    try:
        async with async_sessionmaker(engine)() as db:
            for oid, cents in [
                ("ORD94071", 31840),
                ("ORD94072", 31940),
                ("ORD93041", 23780),
                ("ORD93042", 58620),
            ]:
                if await db.get(OrderRow, oid) is None:
                    db.add(
                        OrderRow(order_id=oid, user_id="u_demo", status="paid", total_cents=cents)
                    )
            await db.commit()
    finally:
        await engine.dispose()


async def history(cfg, case, arm):
    session = "sess_p4d_" + case["id"] + "_" + arm
    engine = create_async_engine(cfg["database_url"])
    try:
        async with async_sessionmaker(engine)() as db:
            if await db.get(SessionRow, session) is not None:
                raise SafetyStop("paired session already exists;no overwrite/replay")
            db.add(SessionRow(session_id=session, user_id="u_demo"))
            await db.flush()
            for role, content in case.get("history", []):
                db.add(MessageRow(session_id=session, role=role, content=content))
            await db.commit()
    finally:
        await engine.dispose()
    return session


def baseline(api):
    path = RUN / "baseline.json"
    if path.exists():
        raise SafetyStop("baseline consumed;no automatic paid replay")
    write(path, dict(status="STARTED", started_at=stamp()))
    rows = []

    def ask(label, payload, **kw):
        row = api.request("baseline", payload, **kw)
        row["label"] = label
        rows.append(row)
        return row

    result = dict(status="INCOMPLETE", objective_success=False)
    try:
        proposal = ask("proposal", dict(message="请取消订单 ORD94071。"))
        assert proposal["status"] == 200 and unchanged(proposal["before"], proposal["after"])
        action = proposal["body"].get("pending_action")
        assert (
            action
            and action["tool_name"] == "cancel_order"
            and action["arguments"]["order_id"] == "ORD94071"
        )
        payload = dict(
            message="确认取消",
            session_id=proposal["body"]["session_id"],
            confirm_action_id=action["action_id"],
            idempotency_key="p4d_baseline_unique",
        )
        denied = ask("cross_user_confirmation", payload, identity="other")
        assert (
            denied["status"] in [400, 403]
            and not denied["tools"]
            and unchanged(denied["before"], denied["after"])
        )
        missing = ask("missing_credentials", dict(message="取消订单 ORD94072"), identity=None)
        assert (
            missing["status"] == 401
            and not missing["tools"]
            and unchanged(missing["before"], missing["after"])
        )
        confirm = ask("confirm", payload)
        assert confirm["status"] == 200
        assert_confirmation_effects(
            proposal["before"],
            confirm["after"],
            "ORD94071",
            action["action_id"],
            {confirm["trace_id"]},
        )
        repeat = ask("idempotent_replay", payload)
        assert repeat["status"] == 200 and unchanged(repeat["before"], repeat["after"])
        assert any(t.get("status") == "replayed" for t in repeat["tools"])
        negative = ask(
            "negative_request",
            dict(message="不要取消订单 ORD94072，只查询订单状态。"),
            protocol="sse",
        )
        assert (
            negative["status"] == 200
            and not negative["body"].get("pending_action")
            and unchanged(negative["before"], negative["after"])
        )
        assert not any(t["name"] == "cancel_order" for t in negative["tools"])
        result.update(
            status="COMPLETED",
            objective_success=True,
            real_cancel="PASS",
            hitl="PASS",
            idempotent_replay="PASS",
            negative_request="PASS",
            unauthorized="PASS",
        )
    except BaseException as exc:
        result.update(error=type(exc).__name__)
        raise
    finally:
        result.update(
            rows=rows,
            totals=Ledger(RUN).totals(),
            full_factual_correctness="NOT_ASSESSED",
            full_faithfulness="NOT_ASSESSED",
        )
        write(path, result)


def pair(api, cfg, case):
    path = RUN / ("pair_" + case["id"] + ".json")
    if path.exists():
        raise SafetyStop("pair consumed/uncertain;no automatic paid replay")
    arms = ["M0", "M1", "M2"] if case["kind"] == "memory" else ["BM25", "DENSE", "HYBRID", "RERANK"]
    if case["split"] == "independent_test":
        arms = list(reversed(arms))
    ledger = Ledger(RUN)
    ledger.admit_pair(len(arms))
    record = dict(
        status="STARTED",
        complete=False,
        case=case,
        arm_order=arms,
        arms={},
        results={},
        reservation=dict(requests=len(arms) * 12, tokens=len(arms) * 20000),
        started_at=stamp(),
    )
    write(path, record)
    try:
        for arm in arms:
            group = case["id"] + "_" + arm
            session = asyncio.run(history(cfg, case, arm))
            before_tokens = Ledger(RUN).totals()
            row = api.request(group, dict(message=case["query"], session_id=session), arm=arm)
            ledger = Ledger(RUN)
            ledger.safe()
            if row.get("status") != 200 or not row.get("protocol_valid"):
                raise SafetyStop("incomplete arm;exclude entire pair")
            result = score(case, row)
            record["arms"][arm] = result["objective_success"]
            record["results"][arm] = dict(
                row=row, score=result, totals_before=before_tokens, totals_after=ledger.totals()
            )
            write(path, record)
            print(case["id"], arm, result["objective_success"], flush=True)
        record.update(status="COMPLETED", complete=True)
    except BaseException as exc:
        record.update(status="INCOMPLETE", error=type(exc).__name__)
        raise
    finally:
        write(path, record)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["baseline", "pairs"])
    args = parser.parse_args()
    verify_freeze()
    RUN.mkdir(parents=True, exist_ok=True)
    manifest, cfg = live_config()
    command(manifest, "ps")
    with exclusive(HERE / ".private/runner_lock"):
        asyncio.run(seed(cfg))
        if args.stage == "pairs":
            if not json.loads((RUN / "baseline.json").read_text()).get("objective_success"):
                raise SafetyStop("critical baseline gate failed")
            if (
                json.loads((HERE / "evidence/d1_ir.json").read_text()).get("real_models")
                is not True
            ):
                raise SafetyStop("real RAG model validation missing")
        api = Api(args.stage, cfg)
        try:
            api.wait()
            if args.stage == "baseline":
                baseline(api)
            else:
                cases = json.loads((HERE / "tasks.json").read_text())["cases"]
                for split in ["development", "independent_test"]:
                    for case in cases:
                        if case["split"] == split:
                            pair(api, cfg, case)
        finally:
            api.stop()
        write(
            RUN / (args.stage + "_summary.json"),
            dict(totals=Ledger(RUN).totals(), stage=args.stage),
        )


if __name__ == "__main__":
    main()
