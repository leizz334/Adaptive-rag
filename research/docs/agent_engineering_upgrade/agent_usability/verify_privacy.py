"""Windows-side protected-history and secret scan; emit counts and relative paths only."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from research.docs.agent_engineering_upgrade.docker_production_acceptance.ops import wsl

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/agent_usability"
baseline = json.loads(
    (
        ROOT
        / "research/docs/agent_engineering_upgrade/windows_workbench/.private/preservation-baseline.json"
    ).read_text()
)
changed = [
    row["path"]
    for row in baseline["files"]
    if not Path(row["path"]).is_file()
    or hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() != row["sha256"]
]
secret_values = json.loads(
    wsl("""
import json
from pathlib import Path
root=Path('/home/panda/.adaptive-rag-usability-20261114')
print(json.dumps(list(json.loads((root/'browser-config.json').read_text())['tokens'].values())+list(json.loads((root/'mock-credentials.json').read_text())['tokens'].values())))
""")
)
secrets = set(secret_values)
for directory in [ROOT, ROOT.parents[1]]:
    file = directory / ".env"
    if file.is_file():
        for line in file.read_text(encoding="utf-8-sig").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if re.search("key|password|token", name, re.I) and len(value) >= 12:
                secrets.add(value)
env = os.environ.copy()
env["GIT_OBJECT_DIRECTORY"] = (
    "C:/Users/panda/.codex/recovery/Adaptive-rag-20261113-467df67775c0485fbcd23b50481ed14a.git/objects"
)
stash = subprocess.check_output(
    ["git", "stash", "list", "--format=%H"], env=env, text=True
).splitlines()
paths = [
    p
    for p in HERE.rglob("*")
    if p.is_file() and not {".private", "__pycache__"}.intersection(p.parts)
]
paths += [
    ROOT / p
    for p in subprocess.check_output(
        ["git", "diff", "--name-only", "fde159a4"], env=env, text=True
    ).splitlines()
    if (ROOT / p).is_file()
]
matches = sorted(
    {str(p.relative_to(ROOT)) for p in paths if any(s.encode() in p.read_bytes() for s in secrets)}
)
result = {
    "protected_files": len(baseline["files"]),
    "protected_files_unchanged": not changed,
    "changed_protected_paths": changed,
    "stash_unchanged": stash == baseline["stash_commits"],
    "secret_match_paths": matches,
    "secrets_scanned": len(secrets),
    "paid_requests": 0,
}
output = sys.argv[1] if len(sys.argv) > 1 else "final-privacy.json"
assert re.fullmatch(r"[a-z0-9-]+\.json", output)
with (HERE / "evidence" / output).open("x") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result))
raise SystemExit(int(bool(changed or matches or stash != baseline["stash_commits"])))
