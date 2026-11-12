"""S1-EX-only durable ledger; audited C transport is reused without changing C."""

import math
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import (
    PRICING,
    Ledger as BaseLedger,
    MeteredTransport as MeteredTransport,
    SafetyStop,
    read,
    write,
)

LIMITS = {"requests": 120, "tokens": 120000, "usd": 1.0}
ARM_REQUESTS = 8
ARM_TOKENS = 24000


class Ledger(BaseLedger):
    def __init__(self, run, *, limits=None):
        self.run = Path(run)
        self.run.mkdir(parents=True, exist_ok=True)
        self.limits = LIMITS | (limits or {})
        if set(self.limits) != set(LIMITS) or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= LIMITS[k]
            for k, v in self.limits.items()
        ):
            raise ValueError("invalid EX hardcap")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []
        if not isinstance(self.rows, list) or any(
            r.get("schema") != "s1ex-request-v1" for r in self.rows
        ):
            raise SafetyStop("foreign/corrupt EX ledger")
        self.group = "unassigned"
        self.fingerprint = None

    def safe(self):
        if any(
            r["status"] != "RESPONSE" or not r.get("usage") or r.get("error") for r in self.rows
        ):
            raise SafetyStop("uncertain/error stops all paid dispatch")

    def admit_triplet(self):
        self.safe()
        t = self.totals()
        if (
            t["http_attempts"] + 3 * ARM_REQUESTS > self.limits["requests"]
            or t["accounted_tokens"] + 3 * ARM_TOKENS > self.limits["tokens"]
            or t["estimated_usd_upper"] + 3 * ARM_TOKENS * max(PRICING.values()) / 1e6
            > self.limits["usd"]
        ):
            raise SafetyStop("complete-triplet conservative reservation unavailable")

    def admit(self, inputs, outputs):
        self.safe()
        t = self.totals()
        group = [r for r in self.rows if r["group"] == self.group]
        used = sum(r["usage"]["total_tokens"] for r in group)
        if (
            self.group == "unassigned"
            or len(group) + 1 > ARM_REQUESTS
            or used + inputs + outputs > ARM_TOKENS
            or t["http_attempts"] + 1 > self.limits["requests"]
            or t["accounted_tokens"] + inputs + outputs > self.limits["tokens"]
            or t["estimated_usd_upper"]
            + (inputs * PRICING["input"] + outputs * PRICING["output"]) / 1e6
            > self.limits["usd"]
        ):
            raise SafetyStop("EX global/arm hardcap")

    def save(self):
        for row in self.rows:
            if row.get("schema") == "p4c-request-v1":
                row["schema"] = "s1ex-request-v1"
        write(self.path, self.rows)
