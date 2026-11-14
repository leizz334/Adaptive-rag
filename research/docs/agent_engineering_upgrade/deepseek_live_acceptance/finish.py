"""Stop only this run's RealDev services, preserve ledger and formal Offline stack."""

import hashlib
import json
import os
import subprocess
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
assert hashlib.sha256((ROOT / ".env").read_bytes()).hexdigest() == baseline["env_sha256"]
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
code = """
import json
from pathlib import Path
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
c=load_runtime_config()
b=AttemptLedger(c.budget_path,c.limits)
print(json.dumps({'ledger':b.snapshot(),'mode':oct(Path(c.budget_path).stat().st_mode&0o777),'key_file_mode':oct(Path('/run/secrets/deepseek_api_key').stat().st_mode&0o777)}))
"""
receipt = json.loads(docker("exec", PROJECT + "-api-1", "python", "-c", code))
tokens = json.loads(
    docker(
        "exec",
        PROJECT + "-api-1",
        "python",
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
