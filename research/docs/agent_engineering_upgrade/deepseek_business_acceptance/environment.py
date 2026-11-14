"""Owned RealDev operations; never touch Offline containers or emit credentials."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

from research.docs.agent_engineering_upgrade.docker_production_acceptance import deploy as offline

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_business_acceptance"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-business-20261114")
PROJECT = "adaptive-rag-real-agent-dev"
API = PROJECT + "-api-1"
IMAGE = "adaptive-rag-production:usability-20261114"
os.umask(0o077)


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, indent=2)


def docker(*args):
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    if p.returncode:
        (PRIVATE / "docker-error.log").write_text(p.stderr)
        raise RuntimeError("Docker failed; diagnostic details retained privately")
    return p.stdout


def compose(*args):
    return docker(
        "compose",
        "--env-file",
        str(PRIVATE / "compose.env"),
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "compose.showcase.yml"),
        "-f",
        str(ROOT / "compose.agent-dev.yml"),
        "-f",
        str(PRIVATE / "image.json"),
        *args,
    )


def rows():
    return json.loads(docker("inspect", *docker("ps", "-aq").split()))


def safe(r):
    return {
        "name": r["Name"],
        "id": r["Id"],
        "image": r["Image"],
        "state": r["State"]["Status"],
        "started": r["State"]["StartedAt"],
        "health": r["State"].get("Health", {}).get("Status"),
        "volumes": [m.get("Name") for m in r["Mounts"] if m["Type"] == "volume"],
        "project": r["Config"]["Labels"].get("com.docker.compose.project"),
    }


if sys.argv[1] == "snapshot":
    actual = rows()
    real = next(r for r in actual if r["Name"] == "/" + API)
    assert real["State"]["Status"] == "exited"
    env = dict(v.split("=", 1) for v in real["Config"]["Env"])
    key_file = Path(
        next(
            m["Source"]
            for m in real["Mounts"]
            if m["Destination"] == "/run/secrets/deepseek_api_key"
        )
    )
    assert not key_file.is_symlink() and key_file.is_file() and key_file.stat().st_mode & 0o077 == 0
    assert key_file.read_text().strip()
    cfg = dotenv_values(ROOT / ".env", encoding="utf-8-sig")
    assert (
        (cfg.get("DEEPSEEK_API_KEY") or "").strip() == key_file.read_text().strip()
    ), "Native private Key differs from configured .env; do not overwrite"
    assert (
        env["DEEPSEEK_MODEL"] == "deepseek-flash"
        and env["DEEPSEEK_BASE_URL"] == "https://api.deepseek.com"
    )
    assert (
        env["REAL_AGENT_INPUT_USD_PER_MILLION"] == "0.30"
        and env["REAL_AGENT_OUTPUT_USD_PER_MILLION"] == "1.20"
    )
    (PRIVATE / "original-real-api.json").write_text(json.dumps(real))
    ledger_code = """
import hashlib,json,sqlite3,shutil,os
from pathlib import Path
p=Path('/ledger/budget.sqlite3')
with sqlite3.connect('file:/ledger/budget.sqlite3?mode=ro',uri=True) as db:
 assert db.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 rows=db.execute('SELECT id,tokens,usd,state FROM attempts ORDER BY id').fetchall()
 metadata=db.execute('SELECT fingerprint FROM metadata').fetchall()
os.umask(0o077)
with Path('/backup/original-budget.sqlite3').open('xb') as f:f.write(p.read_bytes())
print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'attempts':rows,'metadata':metadata}))
"""
    ledger = json.loads(
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "-v",
            PROJECT + "_real_budget:/ledger:ro",
            "-v",
            str(PRIVATE) + ":/backup:rw",
            "--entrypoint",
            "python",
            IMAGE,
            "-c",
            ledger_code,
        )
    )
    import shutil
    from decimal import Decimal

    from app.providers.paid_budget import AttemptLedger, BudgetBlocked, BudgetLimits

    original = BudgetLimits(
        6, 10000, Decimal("0.05"), Decimal("0.30"), Decimal("1.20"), "deepseek-flash"
    )
    copy_dir = PRIVATE / "preflight-copy"
    copy_dir.mkdir(mode=0o700)
    shutil.copyfile(PRIVATE / "original-budget.sqlite3", copy_dir / "budget.sqlite3")
    os.chmod(copy_dir / "budget.sqlite3", 0o600)
    snapshot = AttemptLedger(copy_dir / "budget.sqlite3", original).snapshot()
    proposed = BudgetLimits(
        snapshot["requests"] + 20,
        snapshot["tokens"] + 50000,
        Decimal(snapshot["usd"]) + Decimal("0.05"),
        Decimal("0.30"),
        Decimal("1.20"),
        "deepseek-flash",
    )
    rejected = False
    try:
        AttemptLedger(copy_dir / "budget.sqlite3", proposed)
    except BudgetBlocked:
        rejected = True
    assert rejected
    compose_env = {
        k: v
        for k, v in env.items()
        if k.startswith("REAL_AGENT_")
        and k not in {"REAL_AGENT_DEV_ENABLED", "REAL_AGENT_PAID_AUTHORIZED"}
    }
    compose_env.update(
        REAL_AGENT_KEY_FILE=str(key_file),
        REAL_AGENT_MODEL="deepseek-flash",
        REAL_AGENT_BASE_URL="https://api.deepseek.com",
        REAL_AGENT_PORT="8001",
        REAL_AGENT_PAID_AUTHORIZED="false",
    )
    with (PRIVATE / "compose.env").open("x") as stream:
        stream.write("".join(k + "=" + v + "\n" for k, v in compose_env.items()))
    (PRIVATE / "image.json").write_text(
        json.dumps({"services": {"api": {"image": IMAGE, "pull_policy": "never"}}})
    )
    save("D1-offline-database.json", offline.fingerprint())
    result = {
        "containers": [safe(r) for r in actual],
        "volumes": docker("volume", "ls", "--format", "{{.Name}}").splitlines(),
        "env_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT / ".env", Path("/mnt/d/Code/Adaptive-rag/.env")]
            if p.is_file()
        },
        "private_key": {
            "path": str(key_file),
            "mode": oct(key_file.stat().st_mode & 0o777),
            "readable": True,
            "matches_env": True,
        },
        "original_budget": ledger,
        "original_snapshot": snapshot,
        "original_limits": {"requests": 6, "tokens": 10000, "usd": "0.05"},
        "proposed_cumulative_limits": {
            "requests": proposed.max_requests,
            "tokens": proposed.max_tokens,
            "usd": str(proposed.max_usd),
        },
        "direct_config_extension_rejected": rejected,
        "new_authorization": {"requests": 20, "tokens": 50000, "usd": "0.05"},
        "price_bounds": {
            "input": "0.30",
            "output": "1.20",
            "unit": "USD per million tokens",
            "source": "https://api-docs.deepseek.com/quick_start/pricing/",
        },
        "model": "deepseek-flash",
        "endpoint": "https://api.deepseek.com",
        "paid_requests": 0,
    }
    save("D1-baseline.json", result)
    print(
        json.dumps(
            {
                "D1": "PASS_WITH_BUDGET_CONFIGURATION_BLOCKER",
                "original_snapshot": snapshot,
                "direct_extension_rejected": rejected,
                "proposed_cumulative_limits": result["proposed_cumulative_limits"],
                "key_readable_private": True,
                "paid_requests": 0,
            }
        )
    )
elif sys.argv[1] in {"start-safe", "verify-safe"}:
    baseline = json.loads((OUT / "D1-baseline.json").read_text())
    current = {r["Name"]: r for r in rows()}
    resolved = json.loads(compose("config", "--format", "json"))
    api = resolved["services"]["api"]
    assert api["environment"]["REAL_AGENT_PAID_AUTHORIZED"] == "false"
    assert api["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 8000,
            "published": "8001",
            "protocol": "tcp",
        }
    ]
    assert api["environment"]["EXPERIENCE_MEMORY_MODE"] == "off"
    assert (
        next(v for v in api["volumes"] if v["target"] == "/var/lib/real-agent")["source"]
        == "real_budget"
    )
    if sys.argv[1] == "start-safe":
        assert not any(
            r["State"]["Running"]
            for r in current.values()
            if r["Config"]["Labels"].get("com.docker.compose.project") == PROJECT
        )
        docker("start", *[PROJECT + "-" + s + "-1" for s in ["postgres", "redis", "qdrant"]])
        for _ in range(45):
            deps = json.loads(
                docker(
                    "inspect", *[PROJECT + "-" + s + "-1" for s in ["postgres", "redis", "qdrant"]]
                )
            )
            if all(r["State"].get("Health", {}).get("Status") == "healthy" for r in deps):
                break
            time.sleep(1)
        else:
            raise RuntimeError("Real dependencies not healthy; no model request")
        compose("up", "-d", "--no-deps", "--no-build", "api")
    with httpx.Client(trust_env=False, timeout=5) as client:
        for _ in range(45):
            try:
                ready = client.get("http://127.0.0.1:8001/api/v1/ready").json()
                if ready.get("ready") and all(d["ready"] for d in ready["dependencies"]):
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Real API startup failed; no model request")
        metadata = client.get("http://127.0.0.1:8001/api/v1/runtime-status").json()
        assert (
            metadata["mode"] == "deepseek"
            and not metadata["verification_only"]
            and metadata["reason"] == "payment_not_authorized"
        )
        credentials = json.loads(
            docker(
                "exec",
                API,
                "python",
                "-c",
                'import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))',
            )
        )
        identities = {}
        for name, token in credentials.items():
            response = client.get(
                "http://127.0.0.1:8001/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
            )
            assert response.status_code == 200
            identities[name] = response.json()
    config_path = PRIVATE / "browser-config.json"
    if config_path.exists():
        assert json.loads(config_path.read_text()) == {"port": 8001, "tokens": credentials}
    else:
        with config_path.open("x") as stream:
            json.dump({"port": 8001, "tokens": credentials}, stream)
    os.chown(PRIVATE / "browser-config.json", 1000, 1000)
    source = docker(
        "exec",
        API,
        "python",
        "-c",
        "import json,hashlib;from pathlib import Path;print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('/app/app/providers/paid_budget.py'),Path('/app/app/providers/usage_settlement.py'),Path('/app/app/demo/real_dev.py')]}))",
    )
    for path, digest in json.loads(source).items():
        assert (
            hashlib.sha256((ROOT / path.removeprefix("/app/")).read_bytes()).hexdigest() == digest
        )
    assert offline.fingerprint() == json.loads((OUT / "D1-offline-database.json").read_text())
    after = rows()
    lifecycle_changes = []
    for r in baseline["containers"]:
        if r["project"] == "adaptive-rag-showcase":
            now = safe(next(n for n in after if n["Name"] == r["name"]))
            assert {k: v for k, v in now.items() if k not in {"started", "health"}} == {
                k: v for k, v in r.items() if k not in {"started", "health"}
            }
            if now["state"] == "running":
                assert now["health"] == "healthy"
            if now["started"] != r["started"]:
                lifecycle_changes.append(
                    {"name": r["name"], "before": r["started"], "now": now["started"]}
                )
    save(
        "D2-safe-startup.json",
        {
            "metadata": metadata,
            "ready": ready,
            "identities": identities,
            "real_containers": [
                safe(r)
                for r in after
                if r["Config"]["Labels"].get("com.docker.compose.project") == PROJECT
            ],
            "current_source_hashes": json.loads(source),
            "offline_container_ids_images_volumes_database_unchanged": True,
            "wsl_restart_start_time_changes": lifecycle_changes,
            "lifecycle_mitigation": "foreground interactive WSL shell during test; no global settings changed",
            "initialize_seed_not_run": True,
            "paid_requests": 0,
        },
    )
    print(
        json.dumps(
            {
                "D2": "PASS",
                "metadata": metadata,
                "auth_identities": len(identities),
                "offline_unchanged": True,
                "paid_requests": 0,
            }
        )
    )
elif sys.argv[1] == "audit-safe":
    baseline = json.loads((OUT / "D1-baseline.json").read_text())
    code = """
import hashlib,json,sqlite3,socket,ssl
from pathlib import Path
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger,_request_reservation
c=load_runtime_config()
b=AttemptLedger(c.budget_path,c.limits)
with sqlite3.connect('file:'+str(c.budget_path)+'?mode=ro',uri=True) as db:
 rows=db.execute('SELECT id,tokens,usd,state FROM attempts ORDER BY id').fetchall()
 metadata=db.execute('SELECT fingerprint FROM metadata').fetchall()
tables=['attempts','metadata','reservation_evidence','settlements']
payload=json.dumps({'model':c.limits.model,'messages':[{'role':'user','content':''}],'max_tokens':1}).encode()
minimum,cost=_request_reservation(payload,c.limits)
network={}
try:
 with socket.create_connection(('api.deepseek.com',443),timeout=8) as sock:
  with ssl.create_default_context().wrap_socket(sock,server_hostname='api.deepseek.com') as tls:
   network={'tls_verified':True,'tls_version':tls.version()}
except Exception as exc:network={'tls_verified':False,'error_type':type(exc).__name__}
print(json.dumps({'snapshot':b.snapshot(),'attempts':rows,'metadata':metadata,'sha256':hashlib.sha256(c.budget_path.read_bytes()).hexdigest(),'migration':'additive reservation_evidence/settlements only','minimum_reservation_tokens':minimum,'minimum_reservation_usd':str(cost),'container_no_auth_tls':network}))
"""
    audit = json.loads(docker("exec", API, "python", "-c", code))
    assert audit["attempts"] == baseline["original_budget"]["attempts"]
    assert audit["metadata"] == baseline["original_budget"]["metadata"]
    assert audit["snapshot"] == baseline["original_snapshot"]
    assert audit["minimum_reservation_tokens"] > 10000 - audit["snapshot"]["tokens"]
    credentials = json.loads((PRIVATE / "browser-config.json").read_text())["tokens"]
    with httpx.Client(trust_env=False, timeout=30) as client:
        response = client.post(
            "http://127.0.0.1:8001/api/v1/chat",
            headers={"Authorization": "Bearer " + credentials["a"]},
            json={"message": "请查询 ORD95101 的订单状态和金额", "user_id": "web_demo_a"},
        )
    assert response.status_code == 503
    after = json.loads(
        docker(
            "exec",
            API,
            "python",
            "-c",
            "import json;from app.demo.real_dev import load_runtime_config;from app.providers.paid_budget import AttemptLedger;c=load_runtime_config();print(json.dumps(AttemptLedger(c.budget_path,c.limits).snapshot()))",
        )
    )
    assert after == audit["snapshot"]
    assert offline.fingerprint() == json.loads((OUT / "D1-offline-database.json").read_text())
    save(
        "D2-safe-audit.json",
        {
            "ledger": audit,
            "paid_disabled_http_status": response.status_code,
            "paid_disabled_response": response.json(),
            "snapshot_unchanged_after_denied_chat": True,
            "original_rows_fingerprint_unchanged": True,
            "original_offline_database_unchanged": True,
            "minimum_old_remaining_tokens": 1014,
            "budget_extension_scope": "awaiting_user_confirmation",
            "paid_requests": 0,
        },
    )
    print(
        json.dumps(
            {
                "audit": "PASS",
                "snapshot": after,
                "minimum_reservation_tokens": audit["minimum_reservation_tokens"],
                "old_remaining_tokens": 1014,
                "disabled_chat_status": response.status_code,
                "container_tls": audit["container_no_auth_tls"],
                "paid_requests": 0,
            }
        )
    )
