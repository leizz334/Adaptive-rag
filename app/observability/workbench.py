"""Bounded local inspection snapshots. Never persist graph state or model inputs."""

import re
import time
from collections import OrderedDict
from copy import deepcopy

from app.core.security import redact_log_text
from app.observability.tracing import _active, safe_metadata


def text(value, limit=160):
    # Redact before truncating, including raw credential-shaped tokens.
    value = redact_log_text(str(value))
    value = re.sub(r"\b[A-Za-z0-9_-]{43,}\b", "[REDACTED]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    return value[:limit]


class WorkbenchStore:
    def __init__(self, *, ttl=900, max_records=128, clock=time.monotonic):
        self.ttl, self.max_records, self.clock = ttl, max_records, clock
        self._records = OrderedDict()

    def put(self, root, subject, session, snapshot):
        now = self.clock()
        self._records = OrderedDict((k, v) for k, v in self._records.items() if v[0] > now)
        self._records[root] = (now + self.ttl, subject, session, deepcopy(snapshot))
        while len(self._records) > self.max_records:
            self._records.popitem(last=False)

    def get(self, root, subject, session):
        row = self._records.get(root)
        if row is None:
            return None
        if row[0] <= self.clock():
            del self._records[root]
            return None
        if row[1:3] != (subject, session):
            return None
        return deepcopy(row[3])


def arguments_summary(arguments):
    if not isinstance(arguments, dict):
        return {}
    patterns = {"order_id": r"ORD[-_]?[0-9]{1,20}", "sku": r"SKU[-_]?[A-Za-z0-9_-]{1,32}"}
    return {
        key: value
        for key, pattern in patterns.items()
        if isinstance(value := arguments.get(key), str) and re.fullmatch(pattern, value)
    }


def result_summary(output):
    if not isinstance(output, dict):
        return {}
    result = {}
    if isinstance(output.get("status"), str) and output.get("status") in {
        "created",
        "paid",
        "shipped",
        "delivered",
        "cancelled",
        "refunding",
        "refunded",
        "requested",
        "processing",
        "completed",
        "pending",
        "failed",
    }:
        result["status"] = output["status"]
    value = output.get("total_cents")
    if type(value) is int and 0 <= value <= 10**12:
        result["total_cents"] = value
    for field, count in [
        ("items", "item_count"),
        ("refunds", "refunds_count"),
        ("tracking_events", "tracking_event_count"),
        ("events", "tracking_event_count"),
    ]:
        if isinstance(output.get(field), list):
            result[count] = min(len(output[field]), 10000)
    return result


def project_state(state, mode):
    plan = state.get("plan")
    return {
        "planner_steps": [
            dict(
                step_id=s.step_id,
                tool_name=text(s.tool_name or ""),
                needs_retrieval=bool(s.needs_retrieval),
                arguments=arguments_summary(getattr(s, "arguments", {})),
            )
            for s in (plan.steps if plan else [])[:12]
        ],
        "tools": [
            dict(
                name=text(s.name),
                success=bool(s.success),
                result=result_summary(getattr(s, "output", {})),
            )
            for s in list(state.get("tool_results") or [])[:20]
        ],
        "retrieval": [
            dict(
                document_id=text(c.document_id),
                chunk_id=text(c.chunk_id),
                title=text(c.title),
                excerpt=text(c.content, 240),
            )
            for c in list(state.get("retrieved_chunks") or [])[:8]
        ],
        "memory": dict(
            mode=mode if mode in {"M0", "M1", "M2", "M3"} else "unknown",
            message_count=min(len(state.get("messages") or []), 10000),
            summary_used=bool(state.get("summary")),
        ),
    }


def capture_state(state, mode, store, *, initial=False):
    run = _active.get()
    if run is None:
        return
    run["workbench_store"] = store
    projected = project_state(state, mode)
    if initial:
        run["workbench_owner"] = (state["user_id"], state["session_id"])
        run["workbench_memory"] = projected["memory"]
    if "workbench_owner" in run:
        projected["memory"] = run["workbench_memory"]
        run["workbench_projection"] = projected


def finalize_snapshot(run):
    store = run.get("workbench_store")
    if store is None or "workbench_owner" not in run:
        return
    subject, session = run["workbench_owner"]
    spans = run["spans"]
    if not spans:
        return
    root = spans[0].id
    snapshot = dict(
        root_run_id=root,
        session_id=session,
        availability=dict(storage="process_local", ttl_seconds=store.ttl),
        **run.get("workbench_projection", {}),
    )
    snapshot["spans"] = [
        dict(
            id=s.id,
            parent_id=s.parent_id,
            name=text(s.name, 80),
            kind=text(s.kind, 24),
            status=s.status,
            latency_ms=round(s.latency_ms, 3),
            metadata=safe_metadata(s.metadata),
        )
        for s in spans[:256]
    ]
    snapshot["nodes"] = [
        text(s.name[5:], 80) for s in spans if s.name.startswith("node.") and s.status == "ok"
    ][:64]
    store.put(root, subject, session, snapshot)
