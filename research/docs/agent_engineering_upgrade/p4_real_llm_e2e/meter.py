"""P4-C only: durable admission and no replay of paid requests."""

import json
import math
import os
import time
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.p2_quality.real import (
    SafetyStop,
    digest,
    exclusive,
    public_response,
    read,
    stage_metadata,
    stamp,
    usage,
    write as base_write,
)


def write(path, value):
    """Sync contents and renamed directory entry before any paid side effect."""
    path = Path(path)
    base_write(path, value)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


LIMITS = dict(requests=80, tokens=80_000, usd=1.0)
PRICING = dict(input=0.30, output=1.20)


class Ledger:
    def __init__(self, run, *, limits=None):
        self.run = Path(run)
        self.run.mkdir(parents=True, exist_ok=True)
        self.limits = LIMITS | (limits or {})
        if set(self.limits) != set(LIMITS) or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= LIMITS[k]
            for k, v in self.limits.items()
        ):
            raise ValueError("cannot expand phase budget")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []
        if not isinstance(self.rows, list) or any(
            r.get("schema") != "p4c-request-v1" for r in self.rows
        ):
            raise SafetyStop("foreign ledger")
        self.group = "preflight"
        self.fingerprint = None

    def totals(self):
        tokens = 0
        cost = 0.0
        for row in self.rows:
            u = usage(row.get("usage"))
            i, o = (
                (u["prompt_tokens"], u["completion_tokens"])
                if u
                else (row["reserve_input"], row["reserve_output"])
            )
            tokens += i + o
            cost += (i * PRICING["input"] + o * PRICING["output"]) / 1_000_000
        return dict(
            http_attempts=len(self.rows),
            accounted_tokens=tokens,
            estimated_usd_upper=cost,
            unknown_usage=sum(usage(r.get("usage")) is None for r in self.rows),
        )

    def admit(self, inputs, outputs):
        if any(
            r["status"] != "RESPONSE" or not usage(r.get("usage")) or r.get("error")
            for r in self.rows
        ):
            raise SafetyStop("uncertain/error ledger: no further paid dispatch")
        t = self.totals()
        if (
            t["http_attempts"] + 1 > self.limits["requests"]
            or t["accounted_tokens"] + inputs + outputs > self.limits["tokens"]
            or t["estimated_usd_upper"]
            + (inputs * PRICING["input"] + outputs * PRICING["output"]) / 1_000_000
            > self.limits["usd"]
        ):
            raise SafetyStop("request admission exceeds hard budget")
        if sum(r["group"] == self.group for r in self.rows) >= 12:
            raise SafetyStop("task group twelve request limit")

    def save(self):
        write(self.path, self.rows)


class MeteredTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger, underlying=None):
        self.ledger = ledger
        self.underlying = underlying or httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        if (
            request.method != "POST"
            or str(request.url) != "https://api.deepseek.com/chat/completions"
        ):
            raise SafetyStop("unpriced endpoint forbidden")
        body = json.loads(request.content)
        if (
            body.get("model") != "deepseek-flash"
            or not 0 < body.get("max_tokens", 0) <= 1024
            or body.get("stream")
        ):
            raise SafetyStop("unfrozen model/output/stream configuration")
        body["thinking"] = {"type": "disabled"}
        raw = json.dumps(body, ensure_ascii=False).encode()
        forwarded = httpx.Request(
            request.method,
            request.url,
            headers={k: v for k, v in request.headers.items() if k != "content-length"},
            content=raw,
        )
        ledger = self.ledger
        with exclusive(ledger.run):
            ledger.rows = read(ledger.path) if ledger.path.exists() else []
            source_fingerprint = digest(ledger.fingerprint()) if ledger.fingerprint else None
            # Recheck frozen inputs before every paid dispatch; preserve source linkage.
            reserve_input, reserve_output = len(raw) + 1024, body["max_tokens"]
            ledger.admit(reserve_input, reserve_output)
            row = dict(
                schema="p4c-request-v1",
                sequence=len(ledger.rows),
                group=ledger.group,
                status="PENDING",
                started_at=stamp(),
                reserve_input=reserve_input,
                reserve_output=reserve_output,
                source_freeze_sha256=source_fingerprint,
                request_sha256=digest(raw),
                prompt_sha256=digest(body["messages"]),
                usage=None,
                **stage_metadata(body),
            )
            ledger.rows.append(row)
            ledger.save()
            started = time.perf_counter()
            try:
                response = await self.underlying.handle_async_request(forwarded)
                await response.aread()
            except BaseException as exc:
                row.update(
                    transport_error=type(exc).__name__,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
                ledger.save()
                raise SafetyStop("uncertain dispatch; preserve reservation, never retry") from None
            clean, error = public_response(response)
            if response.status_code != 200:
                clean, error = dict(choices=[], usage=None), f"HTTP_{response.status_code}"
            if (
                clean.get("model") not in {"deepseek-flash", "DeepSeek-V4.1-Flash-1017"}
                and response.status_code == 200
            ):
                error = "UNVERIFIED_RESPONSE_MODEL"
            u = usage(clean.get("usage"))
            if not u:
                error = error or "MISSING_USAGE"
            elif u["prompt_tokens"] > reserve_input or u["completion_tokens"] > reserve_output:
                error = "USAGE_EXCEEDS_RESERVATION"
            row.update(
                status="RESPONSE",
                response=clean,
                usage=u,
                error=error,
                http_status=response.status_code,
                latency_ms=(time.perf_counter() - started) * 1000,
                completed_at=stamp(),
            )
            ledger.save()
            if error:
                raise SafetyStop("provider response anomaly; stop further paid requests")
            return httpx.Response(200, json=clean, request=request)

    async def aclose(self):
        await self.underlying.aclose()
