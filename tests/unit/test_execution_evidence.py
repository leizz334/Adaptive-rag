import asyncio

import pytest
from pydantic import BaseModel

from app.core.exceptions import InvalidRequestError, ToolExecutionError
from app.observability.execution import capture_tools
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext


class Input(BaseModel):
    value: int


class Read(Tool):
    name = "read"
    input_model = Input

    async def execute(self, parsed, context):
        await asyncio.sleep(0)
        if parsed.value < 0:
            raise OSError("synthetic dependency failure")
        return ToolResult(name=self.name, success=True, output={"value": parsed.value})


async def test_actual_tool_validation_execution_and_failure_events():
    context = ToolContext(user_id="u", session_id="s", trace_id="t")
    with capture_tools() as events:
        result = await Read().run({"value": "2"}, context)
        assert result.output == {"value": 2}
        with pytest.raises(InvalidRequestError):
            await Read().run({"value": "bad"}, context)
        with pytest.raises(ToolExecutionError):
            await Read().run({"value": -1}, context)
    assert [e["success"] for e in events] == [True, False, False]
    assert events[0]["arguments"] == {"value": 2}
    assert [e["failure_kind"] for e in events] == [None, "invalid_arguments", "execution_error"]


async def test_concurrent_evidence_scopes_do_not_mix():
    async def one(value):
        with capture_tools() as events:
            await Read().run(
                {"value": value}, ToolContext(user_id="u", session_id="s", trace_id="t")
            )
        return events

    a, b = await asyncio.gather(one(1), one(2))
    assert [e["arguments"]["value"] for e in a] == [1]
    assert [e["arguments"]["value"] for e in b] == [2]
