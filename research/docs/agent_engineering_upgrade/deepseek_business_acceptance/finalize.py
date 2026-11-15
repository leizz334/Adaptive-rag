"""Read-only final data and paid-gate verification; no model request can be dispatched."""

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.docker_production_acceptance import deploy as offline

ROOT = Path.cwd()
OUT = ROOT / "research/docs/agent_engineering_upgrade/deepseek_business_acceptance/evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-business-20261114")
API = "adaptive-rag-real-agent-dev-api-1"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    assert result.returncode == 0, "Read-only final inspection failed; details withheld"
    return result.stdout


baseline = json.loads((OUT / "B0-baseline.json").read_text())
rows = json.loads(docker("inspect", *docker("ps", "-aq").split()))
for original in baseline["offline_containers"]:
    current = next(r for r in rows if r["Name"] == original["name"])
    assert current["Id"] == original["id"] and current["Image"] == original["image"]
    assert current["State"]["StartedAt"] == original["started"]
    assert [m.get("Name") for m in current["Mounts"] if m["Type"] == "volume"] == original[
        "volumes"
    ]
assert offline.fingerprint() == baseline["offline_database"]
assert all(
    hashlib.sha256(Path(p).read_bytes()).hexdigest() == value
    for p, value in baseline["env_hashes"].items()
)
volumes = docker("volume", "ls", "--format", "{{.Name}}").splitlines()
assert set(volumes) == set(baseline["volumes"])
running = [r for r in rows if r["State"]["Running"]]
assert len(running) == 8 and all(r["State"]["Health"]["Status"] == "healthy" for r in running)
real = next(r for r in rows if r["Name"] == "/" + API)
env = dict(v.split("=", 1) for v in real["Config"]["Env"])
assert env["REAL_AGENT_PAID_AUTHORIZED"] == "false" and env["EXPERIENCE_MEMORY_MODE"] == "off"
assert "adaptive-rag-real-agent-dev_real_budget" in [m.get("Name") for m in real["Mounts"]]
key = Path(
    next(m["Source"] for m in real["Mounts"] if m["Destination"] == "/run/secrets/deepseek_api_key")
)
assert key.is_file() and not key.is_symlink() and key.stat().st_mode & 0o077 == 0
code = """
import json,sqlite3
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger,BudgetBlocked
c=load_runtime_config();b=AttemptLedger(c.budget_path,c.limits,authorization_id=c.authorization_id)
with sqlite3.connect('file:'+str(c.budget_path)+'?mode=ro',uri=True) as db:
 old=db.execute('SELECT id,tokens,usd,state FROM attempts WHERE id<=3 ORDER BY id').fetchall()
 metadata=db.execute('SELECT fingerprint FROM metadata').fetchall()
 closures=db.execute('SELECT * FROM authorization_closures').fetchall()
 selected=db.execute('SELECT * FROM authorizations').fetchall()
blocked=False
try:b.check_capacity(json.dumps({'model':c.limits.model,'messages':[{'role':'user','content':'closed grant'}],'max_tokens':1}).encode())
except BudgetBlocked:blocked=True
print(json.dumps({'snapshot':b.snapshot(),'grant':b.authorization_snapshot(),'old_attempts':old,'metadata':metadata,'authorizations':selected,'closure_witnesses':closures,'closed_capacity_blocked':blocked}))
"""
ledger = json.loads(docker("exec", API, "python", "-c", code))
assert (
    ledger["old_attempts"] == baseline["ledger"]["old_attempts"]
    and ledger["metadata"] == baseline["ledger"]["metadata"]
)
assert ledger["closed_capacity_blocked"] and ledger["grant"]["closed"]
assert ledger["grant"]["requests"] == 20 and ledger["grant"]["max_tokens"] is None
assert (
    Decimal(ledger["grant"]["usd"]) <= Decimal("0.05")
    and ledger["grant"]["pending"] == ledger["grant"]["uncertain"] == 0
)
tokens = json.loads((PRIVATE / "browser-config.json").read_text())["tokens"]
with httpx.Client(trust_env=False, timeout=5) as client:
    status = client.get("http://127.0.0.1:8001/api/v1/runtime-status").json()
    assert (
        status["reason"] == "payment_not_authorized"
        and not status["available"]
        and not status["verification_only"]
    )
    assert client.get("http://127.0.0.1:8000/api/v1/health").status_code == 200
    response = client.post(
        "http://127.0.0.1:8001/api/v1/chat",
        headers={"Authorization": "Bearer " + tokens["a"]},
        json={"message": "closed authorization check"},
    )
    assert response.status_code == 503
assert json.loads(docker("exec", API, "python", "-c", code))["snapshot"] == ledger["snapshot"]

cases = []
for name in ["order", "memory", "rag", "negative", "hitl"]:
    raw = json.loads((OUT / f"B3-{name}.json").read_text())
    review_path = OUT / f"B3-{name}-business-review.json"
    review = json.loads(review_path.read_text()) if review_path.is_file() else None
    if review:
        assert (
            review["source_evidence_sha256"]
            == hashlib.sha256((OUT / f"B3-{name}.json").read_bytes()).hexdigest()
        )
        assert review["business_status"] == "PASS" and review["no_model_replay"]
    usage = raw["actual_usage"]
    estimated = (
        Decimal(usage["prompt_tokens"]) * Decimal("0.30")
        + Decimal(usage["completion_tokens"]) * Decimal("1.20")
    ) / Decimal(1_000_000)
    cases.append(
        {
            "scenario": name,
            "business_status": "PASS"
            if review
            else "NOT_RUN"
            if raw["status"] == "BUDGET_BLOCKED"
            else raw["status"],
            "original_harness_status": raw["status"],
            "reason": raw.get("reason"),
            "additional_review": review_path.name if review else None,
            "actual_model_http_requests": raw["actual_model_http_requests"],
            "usage": usage,
            "latency_ms": sum(r.get("latency_ms", 0) for r in raw.get("requests", [])),
            "usage_cost_upper_usd": str(estimated),
            "ledger_charge_usd": raw["settled_usage_cost_usd"],
        }
    )
total = {
    k: sum(c["usage"][k] for c in cases)
    for k in ["prompt_tokens", "completion_tokens", "total_tokens"]
}
assert sum(c["actual_model_http_requests"] for c in cases) == 20 and total["total_tokens"] == 13791
spans = [
    s
    for name in ["order", "memory", "rag", "negative"]
    for r in json.loads((OUT / f"B3-{name}.json").read_text())["requests"]
    for s in r.get("trace", {}).get("spans", [])
    if s.get("kind") == "llm"
]
assert len(spans) == 20 and all(s["status"] == "ok" and s["metadata"]["usage_known"] for s in spans)
result = {
    "date": "2026-11-15",
    "cases": cases,
    "actual_model_http_requests": 20,
    "supplier_successful_responses": 20,
    "actual_token_usage_from_trace": total,
    "usage_cost_upper_usd": str(
        sum((Decimal(c["usage_cost_upper_usd"]) for c in cases), Decimal(0))
    ),
    "new_grant_occupancy_usd": ledger["grant"]["usd"],
    "new_grant": ledger["grant"],
    "lifetime": ledger["snapshot"],
    "first_five_completed_reservations_never_refunded": True,
    "real_wire_encoding_of_first_five_unknown": True,
    "paid_authorization": False,
    "grant_permanently_closed": True,
    "disabled_chat_status": response.status_code,
    "disabled_probe_new_model_requests": 0,
    "offline_containers_images_volumes_started_times_database_unchanged": True,
    "env_files_unchanged": True,
    "key_mode": oct(key.stat().st_mode & 0o777),
    "original_attempts_fingerprint_preserved": True,
    "volumes": volumes,
    "running_containers": [
        {"name": r["Name"], "image": r["Image"], "health": r["State"]["Health"]["Status"]}
        for r in running
    ],
    "ledger_evidence": ledger,
    "supplier_bill_verified": False,
}
with (OUT / "B4-final-summary.json").open("x") as stream:
    json.dump(result, stream, indent=2)
print(
    json.dumps(
        {
            "verification": "PASS",
            "cases": [{"case": c["scenario"], "status": c["business_status"]} for c in cases],
            "requests": 20,
            "tokens": total,
            "usage_cost_upper_usd": result["usage_cost_upper_usd"],
            "ledger_occupancy_usd": result["new_grant_occupancy_usd"],
            "paid": False,
            "grant_closed": True,
            "running": 8,
            "volumes": len(volumes),
            "offline_unchanged": True,
        }
    )
)
