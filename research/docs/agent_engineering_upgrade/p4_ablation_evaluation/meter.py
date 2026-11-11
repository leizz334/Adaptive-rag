"""D-only global budget; reuse audited no-replay C transport without changing C."""

import math
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.meter import (
    PRICING,
    Ledger as CLedger,
    MeteredTransport as MeteredTransport,
    SafetyStop,
    read,
    write,
)

LIMITS = dict(requests=180, tokens=160000, usd=1.0)
ARM_TOKENS = 20000
ARM_REQUESTS = 12


class Ledger(CLedger):
    def __init__(self, run, *, limits=None):
        self.run = Path(run)
        self.run.mkdir(parents=True, exist_ok=True)
        self.limits = LIMITS | (limits or {})
        if set(self.limits) != set(LIMITS) or any(
            type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= LIMITS[k]
            for k, v in self.limits.items()
        ):
            raise ValueError("invalid D hardcap")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []
        if not isinstance(self.rows, list) or any(
            r.get("schema") != "p4d-request-v1" for r in self.rows
        ):
            raise SafetyStop("foreign/corrupt D ledger")
        self.group = "baseline"
        self.fingerprint = None

    def safe(self):
        if any(
            r["status"] != "RESPONSE" or not r.get("usage") or r.get("error") for r in self.rows
        ):
            raise SafetyStop("uncertain/error row blocks all paid admission")

    def admit_pair(self, arms):
        self.safe()
        t = self.totals()
        if (
            t["http_attempts"] + arms * ARM_REQUESTS > self.limits["requests"]
            or t["accounted_tokens"] + arms * ARM_TOKENS > self.limits["tokens"]
            or t["estimated_usd_upper"] + arms * ARM_TOKENS * max(PRICING.values()) / 1e6
            > self.limits["usd"]
        ):
            raise SafetyStop("whole-pair reservation unavailable;do not start any arm")

    def admit(self, inputs, outputs):
        self.safe()
        t = self.totals()
        group = [r for r in self.rows if r["group"] == self.group]
        per_tokens = 30000 if self.group == "baseline" else ARM_TOKENS
        per_requests = 24 if self.group == "baseline" else ARM_REQUESTS
        used = sum(
            (r.get("usage") or {}).get("total_tokens", r["reserve_input"] + r["reserve_output"])
            for r in group
        )
        if (
            t["http_attempts"] + 1 > self.limits["requests"]
            or t["accounted_tokens"] + inputs + outputs > self.limits["tokens"]
            or t["estimated_usd_upper"]
            + (inputs * PRICING["input"] + outputs * PRICING["output"]) / 1e6
            > self.limits["usd"]
            or len(group) + 1 > per_requests
            or used + inputs + outputs > per_tokens
        ):
            raise SafetyStop("D global/arm admission exhausted")

    def save(self):
        for row in self.rows:
            if row.get("schema") == "p4c-request-v1":
                row["schema"] = "p4d-request-v1"
        write(self.path, self.rows)
