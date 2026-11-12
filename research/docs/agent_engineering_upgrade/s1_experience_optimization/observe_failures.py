"""Post-experiment verified field omissions become unreviewed proposals, never activation."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.experience.contracts import FailureSignal, FailureType, Proof
from app.experience.shadow import EvidenceResolver, ShadowObserver
from app.experience.storage import ExperienceRepository, initialize_schema
from app.experience.taxonomy import classify_failure
from app.main import create_app  # noqa: F401

from .common import HERE, RUN, STATE, read, ref, save, scope_for, sha


async def main():
    path = HERE / ".private/observed_failure_proposals.sqlite3"
    assert not path.exists(), "do not overwrite observed proposal run"
    engine = create_async_engine("sqlite+aiosqlite:///" + str(path))
    await initialize_schema(engine, isolated=True)
    repo = ExperienceRepository(
        async_sessionmaker(engine, expire_on_commit=False), resolver=EvidenceResolver(STATE)
    )
    out = []
    for task in read(HERE / "tasks.json")["tasks"]:
        ids = {
            t["arguments"]["order_id"]
            for t in task["required_tools"]
            if t["name"] == "get_order_items"
        }
        names = [
            item["name"] for o in task["orders"] if o["order_id"] in ids for item in o["items"]
        ]
        if not names:
            continue
        for arm in ["E0", "E1", "E2"]:
            capture = RUN / (task["id"] + "_" + arm + ".json")
            data = read(capture)
            missing = [name for name in names if name not in data["body"]["answer"]]
            if not missing:
                continue
            provided = [
                item["name"]
                for t in data["tools"]
                if t["name"] == "get_order_items" and t["success"]
                for item in t["output"]["items"]
            ]
            assert set(names) <= set(provided)
            assessment = classify_failure(
                source_trace_id=task["id"] + "_" + arm,
                source_case_id=task["id"],
                source_version=sha(HERE / "freeze.json"),
                signals=[
                    FailureSignal(
                        category=FailureType.GOAL_OMISSION,
                        proof=Proof.TRACE_CONTRACT,
                        node="public_final_answer",
                        position=1,
                        evidence_refs=[
                            ref(capture, "request", "/body/answer"),
                            ref(capture, "tool", "/tools"),
                        ],
                        summary="POSTHOC structuralaudit:requested literal item-name fields absent from finalanswer although successfultoolsreturned them",
                        context_tags=["live_fact", "multi_goal"],
                    )
                ],
            )
            scoped = scope_for(data["session"])
            values = []

            async def sink(candidate, values=values, scoped=scoped):
                values.append(await repo.propose(scoped, candidate))

            observer = ShadowObserver(mode="shadow", resolver=EvidenceResolver(STATE), sink=sink)
            outcome = await observer.observe(data, assessment, scoped, completed=True)
            assert outcome.status == "PROPOSED"
            candidate = await repo.transition(
                scoped, values[0].experience_id, "NEEDS_REVIEW", expected_version=values[0].version
            )
            out.append(
                {
                    "case": task["id"],
                    "arm": arm,
                    "missing_names": missing,
                    "assessment": assessment.model_dump(mode="json"),
                    "candidate": candidate.model_dump(mode="json"),
                    "eligible_for_current_E2": False,
                }
            )
    save(
        HERE / "observed_failure_candidates.json",
        {
            "method": "POSTHOC_LITERAL_FIELD_AUDIT_NOT_FROZEN_SCORE_REWRITE",
            "new_proposals": out,
            "review_status": "UNREVIEWED",
            "validation_status": "NEEDS_REVIEW",
            "new_injection_permits": 0,
            "old_paid_store_unchanged": True,
            "production_active": False,
        },
    )
    await engine.dispose()
    print("newunreviewedcurrent-failureproposals", len(out), "noinjectionpermission")


if __name__ == "__main__":
    asyncio.run(main())
