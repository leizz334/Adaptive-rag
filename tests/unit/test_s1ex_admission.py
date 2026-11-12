from unittest.mock import AsyncMock

import pytest

from app.experience.shadow import EvidenceResolver
from app.main import create_app  # noqa: F401
from app.prompts.planner import PLANNER_SYSTEM
from app.tools.factory import build_tool_registry
from research.docs.agent_engineering_upgrade.s1_experience_optimization.common import STATE
from research.docs.agent_engineering_upgrade.s1_experience_optimization.meter import SafetyStop
from research.docs.agent_engineering_upgrade.s1_experience_optimization.worker import (
    CURRENT,
    ExperienceLLM,
)


@pytest.mark.asyncio
async def test_e2_without_qualified_experience_cannot_dispatch(tmp_path):
    provider = AsyncMock()
    wrapper = ExperienceLLM(
        provider, None, build_tool_registry(object()), {}, EvidenceResolver(STATE), tmp_path
    )
    token = CURRENT.set(
        {"arm": "E2", "session": "unqualified", "query": "退货政策是什么", "group": "unqualified"}
    )
    try:
        with pytest.raises(SafetyStop):
            await wrapper.generate(
                [
                    {
                        "role": "system",
                        "content": PLANNER_SYSTEM.format(tools="fixture", skill_context="fixture"),
                    }
                ]
            )
        provider.generate.assert_not_awaited()
    finally:
        CURRENT.reset(token)


@pytest.mark.asyncio
async def test_actual_planner_injection_evidence_is_recorded_before_dispatch(tmp_path):
    import json

    from app.experience.contracts import EvidenceRef
    from app.experience.reflection import ExperienceCandidate
    from research.docs.agent_engineering_upgrade.p4_api_e2e.worker import CASE
    from research.docs.agent_engineering_upgrade.s1_experience_optimization.common import (
        HERE,
        read,
        scope_for,
    )

    task = read(HERE / "tasks.json")["tasks"][0]
    session = task["sessions"]["E2"]
    scope = scope_for(session)

    class Repository:
        async def list(self, _):
            return [
                ExperienceCandidate.model_validate(x)
                for x in read(HERE / "qualified_test_records.json")
                if x["scope"] == scope.model_dump()
            ]

    provider = AsyncMock()
    permits = {k: EvidenceRef.model_validate(v) for k, v in read(HERE / "permits.json").items()}
    wrapper = ExperienceLLM(
        provider,
        Repository(),
        build_tool_registry(object()),
        permits,
        EvidenceResolver(STATE),
        tmp_path,
    )
    token = CURRENT.set(
        {"arm": "E2", "session": session, "query": task["query"], "group": "test_group"}
    )
    case_token = CASE.set("test_group")
    try:
        await wrapper.generate(
            [
                {
                    "role": "system",
                    "content": PLANNER_SYSTEM.format(tools="fixture", skill_context="fixture"),
                }
            ]
        )
        events = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
        assert (
            len(events) == 1
            and events[0]["kind"] == "experience_planner"
            and events[0]["injected"] == 2
        )
        provider.generate.assert_awaited_once()
    finally:
        CURRENT.reset(token)
        CASE.reset(case_token)
