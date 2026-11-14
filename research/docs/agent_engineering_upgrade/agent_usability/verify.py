"""Final read-only Docker, original ledger, environment and order preservation checks."""

import hashlib
import json
import sqlite3
import subprocess
from decimal import Decimal
from pathlib import Path

import httpx

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/agent_usability"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-usability-20261114")
baseline = json.loads((OUT / "baseline.json").read_text())


def docker(*args, binary=False):
    result = subprocess.run(["docker", *args], capture_output=True, text=not binary)
    assert result.returncode == 0, "Read-only Docker inspection failed; private output withheld"
    return result.stdout


rows = json.loads(docker("inspect", *docker("ps", "-aq").split()))
by_name = {r["Name"]: r for r in rows}
formal = [
    by_name["/adaptive-rag-showcase-" + name + "-1"]
    for name in ["api", "postgres", "redis", "qdrant"]
]
assert all(r["State"]["Running"] and r["State"]["Health"]["Status"] == "healthy" for r in formal)
assert formal[0]["Image"] == json.loads((OUT / "P3-image-final.json").read_text())["image_id"]
for old in baseline["containers"]:
    if old["name"] == "/adaptive-rag-showcase-api-1":
        continue
    current = by_name[old["name"]]
    assert (
        current["Id"] == old["id"]
        and current["Image"] == old["image"]
        and current["State"]["Status"] == old["state"]
    )
running = [r["Name"] for r in rows if r["State"]["Running"]]
assert set(running) == {r["Name"] for r in formal}
volumes = docker("volume", "ls", "--format", "{{.Name}}").splitlines()
assert set(baseline["volumes"]).issubset(volumes)
env_hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in baseline["env_sha256"]}
assert env_hashes == baseline["env_sha256"]
assert "EXPERIENCE_MEMORY_MODE=off" in formal[0]["Config"]["Env"]
worker = json.loads((PRIVATE / "worker.json").read_text())
assert not Path("/proc", str(worker["pid"])).exists()

original_real = next(
    r for r in baseline["containers"] if r["name"] == "/adaptive-rag-real-agent-dev-api-1"
)
ledger_script = """
import hashlib,json,sqlite3
from decimal import Decimal
from pathlib import Path
p=Path('/ledger/budget.sqlite3')
with sqlite3.connect('file:/ledger/budget.sqlite3?mode=ro',uri=True) as db:
 rows=db.execute('SELECT id,tokens,usd,state FROM attempts ORDER BY id').fetchall()
 assert db.execute('PRAGMA quick_check').fetchall()==[('ok',)]
print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'attempts':rows,'requests':len(rows),'tokens':sum(r[1] for r in rows),'usd':str(sum((Decimal(r[2]) for r in rows),Decimal(0))),'mode':oct(p.stat().st_mode&0o777)}))
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
        "adaptive-rag-real-agent-dev_real_budget:/ledger:ro",
        "--entrypoint",
        "python",
        original_real["image"],
        "-c",
        ledger_script,
    )
)
assert ledger == baseline["original_budget"]

before = json.loads((OUT / "before-data.json").read_text())
fixture = json.loads((OUT / "P3-browser-fixture.json").read_text())["synthetic_cancel_order"]
assert fixture.startswith("ORD") and fixture[3:].isdigit()
order_hashes = {}
for table in ["orders", "order_items"]:
    sql = f"SELECT row_to_json(t)::text FROM {table} t WHERE order_id <> '{fixture}' ORDER BY row_to_json(t)::text"
    data = docker(
        "exec",
        "adaptive-rag-showcase-postgres-1",
        "psql",
        "-U",
        "adaptive",
        "-d",
        "adaptive_showcase",
        "-Atc",
        sql,
        binary=True,
    )
    record = {"sha256": hashlib.sha256(data).hexdigest(), "rows": len(data.splitlines())}
    assert record == before[table]
    order_hashes[table] = record

assets = {
    str(p.relative_to(ROOT / "frontend/dist")): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (ROOT / "frontend/dist").rglob("*")
    if p.is_file()
}
image_assets = json.loads(
    docker(
        "exec",
        "adaptive-rag-showcase-api-1",
        "python",
        "-c",
        "import hashlib,json;from pathlib import Path;p=Path('/app/frontend/dist');print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}))",
    )
)
# The incremental image retains unused, content-addressed bundles from its base.
# The current index and every current asset must exactly match the frozen build.
assert all(image_assets.get(name) == digest for name, digest in assets.items())
with httpx.Client(trust_env=False, timeout=5) as client:
    assert client.get("http://127.0.0.1:8000/api/v1/health").status_code == 200
    metadata = client.get("http://127.0.0.1:8000/api/v1/runtime-status").json()
    assert (
        metadata["mode"] == "offline"
        and metadata["available"]
        and not metadata["verification_only"]
    )
    try:
        client.get("http://127.0.0.1:8001/api/v1/runtime-status")
    except httpx.TransportError:
        pass
    else:
        raise AssertionError("Owned Mock port8001 still running")
with sqlite3.connect(
    "file:" + str(PRIVATE / "mock-budget/budget.sqlite3") + "?mode=ro", uri=True
) as db:
    attempts = db.execute("SELECT tokens,usd,state FROM attempts").fetchall()
    settlements = db.execute("SELECT total_tokens,usd FROM settlements").fetchall()
    assert all(r[2] == "completed" for r in attempts) and len(attempts) == len(settlements)
mock_ledger = {
    "requests": len(attempts),
    "reserved_tokens": sum(r[0] for r in attempts),
    "tokens": sum(r[0] for r in settlements),
    "reserved_usd": str(sum((Decimal(r[1]) for r in attempts), Decimal(0))),
    "usd": str(sum((Decimal(r[1]) for r in settlements), Decimal(0))),
    "settled": len(settlements),
    "pending": 0,
    "uncertain": 0,
    "simulated_usage_only": True,
}
result = {
    "running_containers": running,
    "running_count": len(running),
    "original_volumes_preserved": True,
    "volumes": volumes,
    "original_container_ids_images_states_preserved_except_upgraded_api": True,
    "original_real_budget": ledger,
    "original_real_budget_unchanged": True,
    "env_files_unchanged": True,
    "existing_orders_items_unchanged": order_hashes,
    "synthetic_browser_cancel_order": fixture,
    "experience_active": "OFF",
    "frontend_image_assets_match_final_source": assets,
    "unreferenced_base_assets_retained": sorted(set(image_assets) - set(assets)),
    "offline_metadata": metadata,
    "mock_worker_stopped": True,
    "mock_ledger_final": mock_ledger,
    "paid_requests": 0,
    "estimated_actual_cost_usd": "0",
}
with (OUT / "final-environment.json").open("x") as stream:
    json.dump(result, stream, indent=2)
print(
    json.dumps(
        {
            "verification": "PASS",
            "running_count": len(running),
            "volume_count": len(volumes),
            "original_ledger_unchanged": True,
            "old_orders_items_unchanged": True,
            "mock_ledger_final": mock_ledger,
            "paid_requests": 0,
        }
    )
)
