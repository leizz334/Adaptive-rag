"""Private hash verification and secret scan of only this phase's public changes."""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
baseline = json.loads((HERE / ".private/preservation-baseline.json").read_text())
checks = []
for row in baseline["files"]:
    path = Path(row["path"])
    actual = None
    if path.is_file():
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
    checks.append({"path": row["path"], "unchanged": actual == row["sha256"]})
changed = [row["path"] for row in checks if not row["unchanged"]]
stash = subprocess.check_output(
    ["git", "stash", "list", "--format=%H"], cwd=ROOT, text=True
).splitlines()
secrets = set()


def remember(value):
    if isinstance(value, str):
        value = value.removeprefix("Bearer ")
        if len(value) >= 12 and not re.search(
            r"example|placeholder|your[_-]|changeme", value, re.I
        ):
            secrets.add(value)


def collect(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r"token|password|authorization|api_key", key, re.I):
                if isinstance(item, dict):
                    for token in item.values():
                        remember(token)
                else:
                    remember(item)
            collect(item)
    elif isinstance(value, list):
        for item in value:
            collect(item)


for repo in [ROOT, ROOT.parents[1]]:
    for filename in [".env", ".env.local"]:
        path = repo / filename
        if path.is_file():
            for name, value in dotenv_values(path).items():
                if re.search(r"key|token|password", name, re.I):
                    remember(value)
                if isinstance(value, str) and "://" in value:
                    try:
                        password = urlsplit(value).password
                        if password:
                            remember(unquote(password))
                    except ValueError:
                        pass
for directory in [
    HERE / ".private",
    ROOT
    / "research/docs/agent_engineering_upgrade/p4_dependency_integration/.private/p4b_ww_w4_20261113_01",
]:
    for path in directory.rglob("*.json"):
        if "browser-" in str(path) or path.name == "preservation-baseline.json":
            continue
        try:
            collect(json.loads(path.read_text(encoding="utf-8-sig")))
        except (ValueError, OSError):
            continue

paths = set(
    subprocess.check_output(
        ["git", "diff", "--name-only", "ab423b5"], cwd=ROOT, text=True
    ).splitlines()
)
untracked = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
).splitlines()
for name in untracked:
    if name.startswith("research/docs/agent_engineering_upgrade/"):
        paths.add(name)
matches = []
for name in sorted(paths):
    path = ROOT / name
    if path.is_file() and ".private" not in path.parts:
        content = path.read_bytes()
        if any(secret.encode() in content for secret in secrets):
            matches.append(name)
result = {
    "protected_file_count": len(checks),
    "protected_files_unchanged": not changed,
    "changed_protected_paths": changed,
    "stash_unchanged": stash == baseline["stash_commits"],
    "secret_candidates_checked": len(secrets),
    "public_change_files_scanned": len(paths),
    "secret_match_paths": matches,
    "backend_experience_unchanged": not any(
        "app/experience/" in path.replace("\\", "/") for path in changed
    ),
}
result["passes"] = not changed and not matches and result["stash_unchanged"]
(HERE / "evidence/W4-preservation-and-secret-scan.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(json.dumps(result))
raise SystemExit(0 if result["passes"] else 1)
