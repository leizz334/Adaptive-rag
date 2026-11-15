"""2026-11-15 continuation: same-ledger admin grant and API-only RealDev image."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.docker_production_acceptance import deploy as offline

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_business_acceptance"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-business-20261114")
API = "adaptive-rag-real-agent-dev-api-1"
PROJECT = "adaptive-rag-real-agent-dev"
GRANT = "business-20261115-20usd005"
IMAGE = "adaptive-rag-real-live:business-20261115"
os.umask(0o077)


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, indent=2)


def docker(*args):
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    if p.returncode:
        (PRIVATE / "business-docker-error.log").write_text(p.stderr)
        raise RuntimeError("Docker operation failed; private diagnostics retained")
    return p.stdout


def compose(*args):
    return docker(
        "compose",
        "--env-file",
        str(PRIVATE / "business.compose.env"),
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "compose.showcase.yml"),
        "-f",
        str(ROOT / "compose.agent-dev.yml"),
        "-f",
        str(PRIVATE / "business-image.json"),
        *args,
    )


def set_configuration(*, paid: bool, grant: str = ""):
    # Original configuration contains paths and prices only; never copy a Key.
    values = dict(
        line.split("=", 1)
        for line in (PRIVATE / "compose.env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    assert values["REAL_AGENT_MAX_REQUESTS"] == "6" and values["REAL_AGENT_MAX_TOKENS"] == "10000"
    assert values["REAL_AGENT_MAX_USD"] == "0.05"
    assert (
        values["REAL_AGENT_INPUT_USD_PER_MILLION"] == "0.30"
        and values["REAL_AGENT_OUTPUT_USD_PER_MILLION"] == "1.20"
    )
    assert values["REAL_AGENT_MODEL"] == "deepseek-flash"
    assert values["REAL_AGENT_BASE_URL"] == "https://api.deepseek.com"
    key = Path(values["REAL_AGENT_KEY_FILE"])
    assert not key.is_symlink() and key.is_file() and key.stat().st_mode & 0o077 == 0
    values.update(
        REAL_AGENT_PAID_AUTHORIZED="true" if paid else "false", REAL_AGENT_AUTHORIZATION_ID=grant
    )
    temporary = PRIVATE / "business.compose.env.new"
    with temporary.open("x") as stream:
        stream.write("".join(k + "=" + v + "\n" for k, v in values.items()))
    temporary.replace(PRIVATE / "business.compose.env")
    (PRIVATE / "business-image.json").write_text(
        json.dumps({"services": {"api": {"image": IMAGE, "pull_policy": "never"}}})
    )


def inspect_ledger():
    code = """
import json,sqlite3,hashlib,os
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
c=load_runtime_config()
b=AttemptLedger(c.budget_path,c.limits,authorization_id=c.authorization_id) if hasattr(c,'authorization_id') else AttemptLedger(c.budget_path,c.limits)
with sqlite3.connect('file:'+str(c.budget_path)+'?mode=ro',uri=True) as db:
 old=db.execute('SELECT id,tokens,usd,state FROM attempts WHERE id<=3 ORDER BY id').fetchall()
 metadata=db.execute('SELECT fingerprint FROM metadata').fetchall()
 settlements=db.execute('SELECT * FROM settlements ORDER BY attempt_id').fetchall()
print(json.dumps({'snapshot':b.snapshot(),'authorization':b.authorization_snapshot() if hasattr(b,'authorization_snapshot') else None,'old_attempts':old,'metadata':metadata,'settlements':settlements,'paid':os.environ.get('REAL_AGENT_PAID_AUTHORIZED'),'grant_id':getattr(c,'authorization_id',None)}))
"""
    return json.loads(docker("exec", API, "python", "-c", code))


def ready():
    with httpx.Client(trust_env=False, timeout=5) as client:
        for _ in range(60):
            try:
                health = client.get("http://127.0.0.1:8001/api/v1/ready").json()
                if health.get("ready") and all(d["ready"] for d in health["dependencies"]):
                    status = client.get("http://127.0.0.1:8001/api/v1/runtime-status").json()
                    assert status["mode"] == "deepseek" and not status["verification_only"]
                    return status
            except httpx.TransportError:
                pass
            time.sleep(1)
    raise RuntimeError("RealDev failed readiness; no model call sent")


if sys.argv[1] == "baseline":
    audit = inspect_ledger()
    original = json.loads((OUT / "D1-baseline.json").read_text())
    assert audit["old_attempts"] == original["original_budget"]["attempts"]
    assert audit["metadata"] == original["original_budget"]["metadata"]
    assert audit["snapshot"]["requests"] == 3 and audit["paid"] == "false"
    assert all(
        hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest
        for p, digest in original["env_hashes"].items()
    )
    rows = json.loads(docker("inspect", *docker("ps", "-aq").split()))
    formal = [
        {
            "id": r["Id"],
            "name": r["Name"],
            "image": r["Image"],
            "started": r["State"]["StartedAt"],
            "volumes": [m.get("Name") for m in r["Mounts"] if m["Type"] == "volume"],
        }
        for r in rows
        if r["Config"]["Labels"].get("com.docker.compose.project") == "adaptive-rag-showcase"
    ]
    backup = """
from pathlib import Path
p=Path('/var/lib/real-agent/budget.sqlite3')
import sys
sys.stdout.buffer.write(p.read_bytes())
"""
    result = subprocess.run(["docker", "exec", API, "python", "-c", backup], capture_output=True)
    assert result.returncode == 0
    with (PRIVATE / "budget-before-grant.sqlite3").open("xb") as stream:
        stream.write(result.stdout)
    save(
        "B0-baseline.json",
        {
            "ledger": audit,
            "offline_containers": formal,
            "offline_database": offline.fingerprint(),
            "volumes": docker("volume", "ls", "--format", "{{.Name}}").splitlines(),
            "env_hashes": original["env_hashes"],
            "backup_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "paid_requests": 0,
        },
    )
    print(json.dumps({"baseline": "PASS", "historical": audit["snapshot"], "paid_requests": 0}))
elif sys.argv[1] in {"build", "build-compression"}:
    suffix = "-compression" if sys.argv[1] == "build-compression" else ""
    context = PRIVATE / ("business-image-context-20261115" + suffix)
    context.mkdir()
    shutil.copytree(
        ROOT / "app", context / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    (context / "Dockerfile").write_text(
        "FROM adaptive-rag-production:usability-20261114\nCOPY --chown=1000:1000 app /app/app\n"
    )
    with (PRIVATE / ("business-image-build" + suffix + ".log")).open("x") as stream:
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE, str(context)], stdout=stream, stderr=stream
        )
    assert result.returncode == 0
    image_id = docker("image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
    save(
        "B1-image" + suffix + ".json",
        {
            "image": IMAGE,
            "image_id": image_id,
            "build_exit": 0,
            "context": "app only, no .env/Key/credentials",
            "paid_requests": 0,
        },
    )
    print(json.dumps({"build": "PASS", "image_id": image_id}))
elif sys.argv[1] in {"upgrade-safe", "upgrade-compression"}:
    compression = sys.argv[1] == "upgrade-compression"
    set_configuration(paid=False, grant=GRANT if compression else "")
    compose("up", "-d", "--no-deps", "--no-build", "api")
    metadata = ready()
    assert metadata["reason"] == "payment_not_authorized"
    audit = inspect_ledger()
    baseline = json.loads((OUT / "B0-baseline.json").read_text())
    assert (
        audit["old_attempts"] == baseline["ledger"]["old_attempts"]
        and audit["metadata"] == baseline["ledger"]["metadata"]
    )
    assert offline.fingerprint() == baseline["offline_database"]
    save(
        "B1-upgrade-compression.json" if compression else "B1-upgrade-safe.json",
        {
            "metadata": metadata,
            "audit": audit,
            "offline_database_unchanged": True,
            "paid_requests": 0,
        },
    )
    print(json.dumps({"upgrade_safe": "PASS", "metadata": metadata, "paid_requests": 0}))
elif sys.argv[1] == "authorize":
    assert inspect_ledger()["paid"] == "false"
    assert json.loads((OUT / "BG-final-tests.json").read_text())["exit"] == 0
    assert json.loads((OUT / "BG-review.json").read_text())["remaining_important_critical"] == 0
    code = """
import json
from decimal import Decimal
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
c=load_runtime_config()
b=AttemptLedger(c.budget_path,c.limits)
b.authorize('business-20261115-20usd005',max_requests=20,max_usd=Decimal('0.05'),max_tokens=None)
selected=AttemptLedger(c.budget_path,c.limits,authorization_id='business-20261115-20usd005')
print(json.dumps(selected.authorization_snapshot()))
"""
    grant = json.loads(docker("exec", API, "python", "-c", code))
    assert (
        grant["requests"] == 0
        and grant["max_tokens"] is None
        and grant["max_requests"] == 20
        and grant["max_usd"] == "0.05"
    )
    set_configuration(paid=False, grant=GRANT)
    compose("up", "-d", "--no-deps", "--no-build", "api")
    assert ready()["reason"] == "payment_not_authorized"
    save(
        "B2-authorization.json",
        {
            "grant": grant,
            "created_by": "trusted local admin after explicit2026-11-15 user authorization",
            "paid_requests": 0,
        },
    )
    print(json.dumps({"authorization": "PASS", "grant": grant, "paid_requests": 0}))
elif sys.argv[1] in {"enable", "resume"}:
    assert (OUT / "B2-authorization.json").is_file()
    resumed = sys.argv[1] == "resume"
    receipt = "B3-paid-resumed.json" if resumed else "B2-paid-enabled.json"
    assert not (OUT / receipt).exists()
    if resumed:
        assert (OUT / "B3-paid-quiesced.json").is_file() and (
            OUT / "B1-upgrade-compression.json"
        ).is_file()
    set_configuration(paid=True, grant=GRANT)
    compose("up", "-d", "--no-deps", "--no-build", "api")
    metadata = ready()
    assert metadata["available"] and metadata["reason"] == "ready"
    audit = inspect_ledger()
    assert audit["authorization"]["requests"] == (5 if resumed else 0) and audit["paid"] == "true"
    assert (
        audit["authorization"]["max_requests"] == 20
        and audit["authorization"]["max_usd"] == "0.05"
        and audit["authorization"]["max_tokens"] is None
    )
    save(
        receipt,
        {
            "metadata": metadata,
            "audit": audit,
            "new_paid_requests_at_enable": 0,
            "existing_grant_attempts_not_reset": resumed,
        },
    )
    print(json.dumps({"enabled": True, "metadata": metadata, "grant": audit["authorization"]}))
elif sys.argv[1] in {"quiesce", "disable"}:
    # Disable transport before closing the ledger grant; never loosen uncertain handling.
    set_configuration(paid=False, grant=GRANT)
    compose("up", "-d", "--no-deps", "--no-build", "api")
    metadata = ready()
    assert not metadata["available"] and metadata["reason"] == "payment_not_authorized"
    if sys.argv[1] == "quiesce":
        save(
            "B3-paid-quiesced.json",
            {
                "metadata": metadata,
                "audit": inspect_ledger(),
                "reason": "diagnose trustworthy usage settlement without more paid requests",
                "grant_not_reset_or_closed": True,
            },
        )
        print(json.dumps({"paid_disabled": True, "grant_retained": True}))
        raise SystemExit(0)
    code = """
import json
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger,BudgetBlocked
c=load_runtime_config();b=AttemptLedger(c.budget_path,c.limits,authorization_id=c.authorization_id)
closed=False
try:b.close_authorization(c.authorization_id);closed=True
except BudgetBlocked:pass
print(json.dumps({'closed':closed,'snapshot':b.snapshot(),'authorization':b.authorization_snapshot()}))
"""
    closure = json.loads(docker("exec", API, "python", "-c", code))
    save(
        "B4-paid-disabled.json",
        {"metadata": metadata, "closure": closure, "unresolved_billing_not_bypassed": True},
    )
    print(
        json.dumps(
            {
                "paid_disabled": True,
                "grant_closed": closure["closed"],
                "authorization": closure["authorization"],
            }
        )
    )
