"""Private immutable preservation manifest; no secret values or Git mutations."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
output = HERE / ".private" / "preservation-baseline.json"
if output.exists():
    raise SystemExit("Baseline already exists; do not overwrite")
files = set()
for directory in [ROOT / "research", ROOT / "app/experience"]:
    files.update(path for path in directory.rglob("*") if path.is_file() and HERE not in path.parents
                 and "__pycache__" not in path.parts)
for repo in [ROOT, ROOT.parents[1]]:
    rows = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--modified", "--others", "--exclude-standard"], text=True)
    for name in rows.splitlines():
        path = repo / name
        if path.is_file() and HERE not in path.parents:
            files.add(path)
    for name in [".env", ".env.local", "AGENTS.md"]:
        if (repo / name).is_file():
            files.add(repo / name)
records = []
for path in sorted(files):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    records.append({"path": str(path), "sha256": digest})
stash = subprocess.check_output(["git", "stash", "list", "--format=%H"], cwd=ROOT, text=True).splitlines()
with output.open("x", encoding="utf-8") as stream:
    json.dump({"files": records, "stash_commits": stash}, stream, indent=2)
print(json.dumps({"protected_files": len(records), "stash_count": len(stash), "manifest": ".private/preservation-baseline.json"}))
