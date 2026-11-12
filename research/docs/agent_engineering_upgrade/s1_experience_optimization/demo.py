"""Portable offline replay from public artifacts. No real inference or business writes."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.nodes.planner import Planner
from app.experience.contracts import EvidenceRef
from app.experience.isolated import prepare_planner
from app.experience.reflection import ExperienceCandidate
from app.experience.shadow import EvidenceResolver
from app.experience.storage import ExperienceRepository, initialize_schema
from app.main import create_app  # noqa: F401
from app.providers.base import LLMResponse
from app.tools.factory import build_tool_registry

from .common import HERE, RUN, STATE, read, scope_for
from .scoring import score

AS_OF = datetime(2026, 11, 12, tzinfo=UTC)


class RecordedPlanner:
    def __init__(self, record, arm, repository, scope, query, registry, permits):
        (
            self.record,
            self.arm,
            self.repository,
            self.scope,
            self.query,
            self.registry,
            self.permits,
        ) = record, arm, repository, scope, query, registry, permits
        self.selected = []
        self.prompt_changed = False

    async def generate(self, messages, **kwargs):
        transformed, self.selected = await prepare_planner(
            messages,
            arm=self.arm,
            repository=self.repository,
            scope=self.scope,
            query=self.query,
            registry=self.registry,
            permits=self.permits,
            resolver=EvidenceResolver(STATE),
            isolated=True,
            now=AS_OF,
        )
        self.prompt_changed = transformed != messages
        # Replays the actual recorded response. It does not manufacture improvement.
        response = self.record["response"]
        return LLMResponse(
            response["choices"][0]["message"]["content"],
            model="RECORDED_DEEPSEEK_RESPONSE_NOT_NEW_INFERENCE",
        )


async def main():
    tasks = read(HERE / "tasks.json")["tasks"]
    task = tasks[0]
    scope = scope_for(task["sessions"]["E2"])
    directory = HERE / ".private/demos" / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    engine = create_async_engine("sqlite+aiosqlite:///" + str(directory / "experience.sqlite3"))
    await initialize_schema(engine, isolated=True)
    resolver = EvidenceResolver(STATE)
    repo = ExperienceRepository(
        async_sessionmaker(engine, expire_on_commit=False), resolver=resolver, clock=lambda: AS_OF
    )
    permits = {k: EvidenceRef.model_validate(v) for k, v in read(HERE / "permits.json").items()}
    public_records = [
        ExperienceCandidate.model_validate(r)
        for r in read(HERE / "qualified_test_records.json")
        if r["scope"] == scope.model_dump()
    ]
    # Rebuild only a new demo DB from committed records through existing governance.
    for record in public_records:
        c = ExperienceCandidate.model_validate(
            record.model_dump()
            | {
                "validation_status": "PROPOSED",
                "review_status": "UNREVIEWED",
                "version": 1,
                "updated_at": record.created_at,
            }
        )
        c = await repo.propose(scope, c)
        c = await repo.transition(
            scope, c.experience_id, "NEEDS_REVIEW", expected_version=c.version
        )
        c = await repo.review(
            scope,
            c.experience_id,
            "MODEL_REVIEWED",
            expected_version=c.version,
            reviewer_kind="model",
        )
        validation = EvidenceRef.model_validate(
            read(HERE / "permits" / f"{c.experience_id}.json")["validation_ref"]
        )
        c = await repo.transition(
            scope,
            c.experience_id,
            "VERIFIED_OFFLINE",
            expected_version=c.version,
            validation_evidence=validation,
        )
        assert c.version == record.version
    registry = build_tool_registry(object())
    ledger = read(RUN / "requests.json")
    plans = []
    for arm in ["E0", "E2"]:
        recorded = next(
            r for r in ledger if r["group"] == task["id"] + "_" + arm and r["stage"] == "planner"
        )
        llm = RecordedPlanner(recorded, arm, repo, scope, task["query"], registry, permits)
        plan = await Planner(llm, registry).create_plan(
            task["query"],
            read(RUN / (task["id"] + "_" + arm + ".json"))["body"]["intent"],
            "",
            raw_query=task["query"],
            order_ids=tuple(o["order_id"] for o in task["orders"]),
        )
        plans.append(
            {
                "arm": arm,
                "selected_families": [c.family for c in llm.selected],
                "prompt_changed": llm.prompt_changed,
                "actual_sanitized_recorded_steps": [
                    {"tool": s.tool_name, "arguments": s.arguments} for s in plan.steps
                ],
            }
        )
    checked = 0
    for t in tasks:
        for arm in ["E0", "E1", "E2"]:
            c = read(RUN / (t["id"] + "_" + arm + ".json"))
            assert c["scores"] == score(
                t, c["body"], c["tools"], c["business_before"] == c["business_after"]
            )
            checked += 1
    result = {
        "demo_mode": "OFFLINE_RECORDED_RESPONSE_REPLAY_NOT_NEW_INFERENCE",
        "historical_as_of": AS_OF.isoformat(),
        "expiry_note": "historical replay clock only;doesnotreactivateexpiredproductionrecords",
        "old_failed_trace": "P2S-PSV22-R0 verifiedtool/goalomission;notrerun",
        "extraction": "canonicaltool_coverage principle derivedfromverifiedfailure",
        "governance": "newdemoSQLite viaPROPOSED->NEEDS_REVIEW->MODEL_REVIEWED->VERIFIED_OFFLINE;publicoriginalrecordsunchanged",
        "planner_reexecution": plans,
        "real_captured_score_replays_verified": checked,
        "real_benefit": "NOT_ESTABLISHED",
        "observed_field_negative": "I01E0/E1namespresent/E2missing;identicalgenerateprompt,notcausallyattributable",
        "current_failure_proposals": read(HERE / "observed_failure_candidates.json")[
            "validation_status"
        ],
        "new_model_requests": 0,
        "new_billed_tokens": 0,
        "human_approvals": 0,
        "production_active": False,
    }
    await engine.dispose()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
