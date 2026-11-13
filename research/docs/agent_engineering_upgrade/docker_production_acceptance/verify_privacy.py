"""Windows-side preservation and secret scan; reports counts and paths only."""

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from research.docs.agent_engineering_upgrade.docker_production_acceptance.ops import wsl

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
baseline = json.loads(
    (
        ROOT
        / "research/docs/agent_engineering_upgrade/windows_workbench/.private/preservation-baseline.json"
    ).read_text()
)
changed = []
for row in baseline["files"]:
    path = Path(row["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        changed.append(row["path"])
tokens = json.loads(
    wsl("""
import subprocess
p=subprocess.run(['docker','exec','adaptive-rag-showcase-api-1','python','-c','import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))'],capture_output=True,text=True,check=True)
print(p.stdout)
""")
)
secrets = set(tokens.values())
for repo in [ROOT, ROOT.parents[1]]:
    file = repo / ".env"
    if file.is_file():
        for line in file.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if re.search(r"key|password|token", name, re.I) and len(value) >= 12:
                secrets.add(value)
matches = []
for file in HERE.rglob("*"):
    if file.is_file() and "__pycache__" not in file.parts:
        content = file.read_bytes()
        if any(secret.encode() in content for secret in secrets):
            matches.append(str(file.relative_to(ROOT)))
env = os.environ.copy()
env["GIT_OBJECT_DIRECTORY"] = (
    "C:/Users/panda/.codex/recovery/Adaptive-rag-20261113-467df67775c0485fbcd23b50481ed14a.git/objects"
)
stash = subprocess.check_output(
    ["git", "stash", "list", "--format=%H"], env=env, text=True
).splitlines()
result = {
    "protected_files": len(baseline["files"]),
    "protected_files_unchanged": not changed,
    "changed_protected_paths": changed,
    "stash_unchanged": stash == baseline["stash_commits"],
    "secret_match_paths": matches,
    "secrets_scanned": len(secrets),
    "paid_dispatch": 0,
}
with (HERE / "evidence/final-privacy.json").open("x") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
raise SystemExit(int(bool(changed or matches or stash != baseline["stash_commits"])))
