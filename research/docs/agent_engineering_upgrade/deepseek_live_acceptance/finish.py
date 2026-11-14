"""Stop only this run's RealDev services, preserve ledger and formal Offline stack."""

import hashlib
import json
import os
import subprocess
import textwrap
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_live_acceptance"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-live-20261114")
PROJECT = "adaptive-rag-real-agent-dev"
os.umask(0o077)


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Final read/stop operation failed; raw output suppressed")
    return result.stdout


baseline = json.loads((OUT / "D1-baseline.json").read_text())
startup = json.loads((OUT / "D2-startup.json").read_text())
owned = startup["containers"]
rows = json.loads(docker("inspect", *[r["id"] for r in owned]))
assert all(r["Config"]["Labels"].get("com.docker.compose.project") == PROJECT for r in rows)
for before in owned:
    current = next(r for r in rows if r["Id"] == before["id"])
    assert (
        current["Image"] == before["image"]
        and [m.get("Name") for m in current["Mounts"]] == before["mounts"]
    )
try:
    assert hashlib.sha256((ROOT / ".env").read_bytes()).hexdigest() == baseline["env_sha256"]
    budget_volume = PROJECT + "_real_budget"
    state_volume = PROJECT + "_showcase_state"
    names = set(docker("volume", "ls", "--format", "{{.Name}}").splitlines())
    assert {budget_volume, state_volume} <= names

    def readonly(*arguments):
        return docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "-v",
            budget_volume + ":/ledger:ro",
            "-v",
            state_volume + ":/var/lib/showcase:ro",
            "--entrypoint",
            "python",
            owned[0]["image"],
            *arguments,
        )

    code = """
import json,sqlite3
from decimal import Decimal
from pathlib import Path
path=Path('/ledger/budget.sqlite3')
with sqlite3.connect('file:/ledger/budget.sqlite3?mode=ro',uri=True) as connection:
 assert connection.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 rows=connection.execute('SELECT tokens,usd,state FROM attempts').fetchall()
 states={state:sum(r[2]==state for r in rows) for state in ['completed','pending','uncertain']}
 ledger={'requests':len(rows),'tokens':sum(r[0] for r in rows),'usd':str(sum((Decimal(r[1]) for r in rows),Decimal(0))),**states}
print(json.dumps({'ledger':ledger,'mode':oct(path.stat().st_mode&0o777)}))
"""
    receipt = json.loads(readonly("-c", textwrap.dedent(code)))
    receipt["verified_with_services_stopped"] = all(not row["State"]["Running"] for row in rows)
    receipt["key_file_mode"] = oct((PRIVATE / "deepseek.key").stat().st_mode & 0o777)
    tokens = json.loads(
        readonly(
            "-c",
            'import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))',
        )
    )
    secrets = {value.encode() for value in tokens.values()}
    secrets.add(
        (dotenv_values(ROOT / ".env", encoding="utf-8-sig").get("DEEPSEEK_API_KEY") or "").encode()
    )
    assert all(secrets)
    matches = []
    for path in HERE.rglob("*"):
        if path.is_file() and ".private" not in path.parts and "__pycache__" not in path.parts:
            if any(secret in path.read_bytes() for secret in secrets):
                matches.append(str(path.relative_to(ROOT)))
    assert not matches, "Secret matches detected; do not publish phase evidence"
    volumes = docker("volume", "ls", "--format", "{{.Name}}").splitlines()
finally:
    # Ownership has already been verified. Scan/read failures must still stop paid services.
    running = [r["Id"] for r in rows if r["State"]["Running"]]
    if running:
        docker("stop", *running)
stopped = json.loads(docker("inspect", *[r["id"] for r in owned]))
assert all(not r["State"]["Running"] for r in stopped)
assert docker("volume", "ls", "--format", "{{.Name}}").splitlines() == volumes
formal = [
    r
    for r in baseline["containers"]
    if r["project"] == "adaptive-rag-showcase"
    and r["name"]
    in ["/adaptive-rag-showcase-" + s + "-1" for s in ["api", "postgres", "redis", "qdrant"]]
]
actual = json.loads(docker("inspect", *[r["id"] for r in formal]))
for before in formal:
    current = next(r for r in actual if r["Id"] == before["id"])
    assert (
        current["Image"] == before["image"]
        and [m.get("Name") for m in current["Mounts"]] == before["mounts"]
    )
    assert current["State"]["Running"] and current["State"]["Health"]["Status"] == "healthy"
with httpx.Client(trust_env=False, timeout=5) as client:
    caps = client.get("http://127.0.0.1:8000/api/v1/capabilities")
    assert caps.status_code == 200 and caps.json()["llm"] == "offline"
result = {
    "real_dev_stopped": True,
    "stopped_names": [r["Name"] for r in stopped],
    "all_volumes_preserved": True,
    "volume_count": len(volumes),
    "retained_real_volumes": [name for name in volumes if name.startswith(PROJECT + "_")],
    "budget_receipt": receipt,
    "env_unchanged": True,
    "secret_match_paths": matches,
    "original_offline_ids_images_mounts_unchanged": True,
    "offline_running_healthy": 4,
    "offline_capabilities": caps.json(),
    "wsl_foreground_session_required": True,
}
with (OUT / "D4-final-runtime.json").open("x") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
