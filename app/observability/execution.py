"""Opt-in in-process execution evidence. NEVER sent to tracing/logging exporters."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

_events: ContextVar[list | None] = ContextVar("local_tool_evidence", default=None)


@contextmanager
def capture_tools():
    events: list[dict] = []
    token = _events.set(events)
    try:
        yield events
    finally:
        _events.reset(token)


def record_tool(name, arguments, *, success=True, status="executed", failure_kind=None):
    events = _events.get()
    if events is None:
        return
    if len(events) >= 1024:
        # Evaluation must fail rather than silently grade incomplete evidence.
        raise RuntimeError("Local execution evidence exceeded 1024 calls")
    events.append(
        dict(
            name=name,
            arguments=deepcopy(arguments),
            success=success,
            status=status,
            failure_kind=failure_kind,
        )
    )
