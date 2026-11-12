import json
from datetime import UTC, datetime

import pytest

from app.experience.contracts import EvidenceRef
from app.experience.isolated import prepare_planner
from app.experience.reflection import ExperienceCandidate
from app.experience.shadow import EvidenceResolver
from app.main import create_app  # noqa: F401
from app.prompts.planner import PLANNER_SYSTEM
from app.tools.factory import build_tool_registry
from research.docs.agent_engineering_upgrade.s1_experience_optimization.common import (
    HERE,
    STATE,
    read,
    scope_for,
)


class Repository:
    def __init__(self, records):
        self.records = records

    async def list(self, scope):
        return self.records


@pytest.mark.asyncio
async def test_qualified_planner_only_max_two_and_shadow_message_identity():
    records = [
        ExperienceCandidate.model_validate(x) for x in read(HERE / "qualified_test_records.json")
    ]
    task = read(HERE / "tasks.json")["tasks"][0]
    scope = scope_for(task["sessions"]["E2"])
    repo = Repository([r for r in records if r.scope.key == scope.key])
    permits = {k: EvidenceRef.model_validate(v) for k, v in read(HERE / "permits.json").items()}
    registry = build_tool_registry(object())
    messages = [
        {
            "role": "system",
            "content": PLANNER_SYSTEM.format(tools="fixture", skill_context="fixture"),
        },
        {"role": "user", "content": task["query"]},
    ]
    original = json.dumps(messages)
    for arm in ["E0", "E1", "E2"]:
        result, selected = await prepare_planner(
            messages,
            arm=arm,
            repository=repo,
            scope=scope,
            query=task["query"],
            registry=registry,
            permits=permits,
            resolver=EvidenceResolver(STATE),
            isolated=True,
            now=datetime(2026, 11, 12, tzinfo=UTC),
        )
        assert len(selected) <= 2
        if arm == "E2":
            assert len(result) == 3 and "HITL" in result[1]["content"]
            assert not any(order["order_id"] in result[1]["content"] for order in task["orders"])
        else:
            assert result == messages
    assert json.dumps(messages) == original
    for role in ["user", "assistant"]:
        untrusted = [messages[0] | {"role": role}, messages[1]]
        result, _ = await prepare_planner(
            untrusted,
            arm="E2",
            repository=repo,
            scope=scope,
            query=task["query"],
            registry=registry,
            permits=permits,
            resolver=EvidenceResolver(STATE),
            isolated=True,
        )
        assert result == untrusted
    result, selected = await prepare_planner(
        messages,
        arm="E2",
        repository=repo,
        scope=scope,
        query=task["query"],
        registry=registry,
        permits={},
        resolver=EvidenceResolver(STATE),
        isolated=True,
    )
    assert result == messages and not selected


@pytest.mark.asyncio
async def test_isolated_entry_refuses_production_or_unverified_scope():
    with pytest.raises(PermissionError):
        await prepare_planner(
            [],
            arm="E2",
            repository=None,
            scope=None,
            query="",
            registry=None,
            permits={},
            resolver=None,
            isolated=False,
        )
