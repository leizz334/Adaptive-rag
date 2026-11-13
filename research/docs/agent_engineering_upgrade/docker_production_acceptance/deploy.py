"""Explicit API-only deployment operations with immutable baseline evidence."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
EVIDENCE = HERE / "evidence"
PRIVATE = Path("/root/.local/state/adaptive-rag-production-20261113")
PROJECT = "adaptive-rag-showcase"
API = PROJECT + "-api-1"
IMAGE = "adaptive-rag-production:be2931f-20261113"
ROLLBACK = "adaptive-rag-production:rollback-20261113"
os.umask(0o077)
PRIVATE.mkdir(parents=True, exist_ok=True, mode=0o700)
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run(*args, binary=False):
    result = subprocess.run(args, capture_output=True, text=not binary, check=False)
    if result.returncode:
        (PRIVATE / "last-command-error").write_bytes(
            result.stderr if binary else result.stderr.encode()
        )
        raise RuntimeError("Command failed; diagnostics retained privately: " + args[0])
    return result.stdout


def save(name, obj):
    with (EVIDENCE / name).open("x") as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False)


def fingerprint():
    pg = PROJECT + "-postgres-1"
    tables = run(
        "docker",
        "exec",
        pg,
        "psql",
        "-U",
        "adaptive",
        "-d",
        "adaptive_showcase",
        "-Atc",
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
    ).splitlines()
    result = {}
    for table in tables:
        assert table.replace("_", "").isalnum()
        data = run(
            "docker",
            "exec",
            pg,
            "psql",
            "-U",
            "adaptive",
            "-d",
            "adaptive_showcase",
            "-Atc",
            'SELECT row_to_json(t)::text FROM "' + table + '" t ORDER BY row_to_json(t)::text',
            binary=True,
        )
        result[table] = {"sha256": hashlib.sha256(data).hexdigest(), "rows": len(data.splitlines())}
    result["alembic_revision"] = run(
        "docker",
        "exec",
        pg,
        "psql",
        "-U",
        "adaptive",
        "-d",
        "adaptive_showcase",
        "-Atc",
        "SELECT version_num FROM alembic_version",
    ).strip()
    return result


def compose(override, *args):
    return run(
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "compose.showcase.yml"),
        "-f",
        str(override),
        *args,
    )


def status():
    rows = json.loads(
        run(
            "docker",
            "inspect",
            *[PROJECT + "-" + s + "-1" for s in ["api", "postgres", "redis", "qdrant"]],
        )
    )
    return [
        {
            "name": r["Name"],
            "id": r["Id"],
            "image": r["Image"],
            "status": r["State"]["Status"],
            "health": r["State"].get("Health", {}).get("Status"),
            "mounts": [m.get("Name") for m in r["Mounts"]],
        }
        for r in rows
    ]


action = sys.argv[1]
if action == "baseline":
    raw = run("docker", "inspect", API, binary=True)
    (PRIVATE / "original-api-inspect.json").write_bytes(raw)
    image = json.loads(raw)[0]["Image"]
    run("docker", "tag", image, ROLLBACK)
    backup = run(
        "docker",
        "exec",
        PROJECT + "-postgres-1",
        "pg_dump",
        "-U",
        "adaptive",
        "-d",
        "adaptive_showcase",
        "--format=custom",
        binary=True,
    )
    with (PRIVATE / "postgres-before.dump").open("xb") as stream:
        stream.write(backup)
    (PRIVATE / "rollback.json").write_text(json.dumps({"services": {"api": {"image": ROLLBACK}}}))
    (PRIVATE / "upgrade.json").write_text(json.dumps({"services": {"api": {"image": IMAGE}}}))
    save("before-data.json", fingerprint())
    save(
        "rollback.json",
        {
            "old_image_id": image,
            "rollback_tag": ROLLBACK,
            "private_directory": str(PRIVATE),
            "command": "docker compose --env-file /dev/null -p adaptive-rag-showcase -f compose.showcase.yml -f "
            + str(PRIVATE / "rollback.json")
            + " up -d --no-deps --no-build api",
            "database_backup": str(PRIVATE / "postgres-before.dump"),
            "initialize_will_not_run": True,
            "status": status(),
        },
    )
    print(
        json.dumps(
            {
                "baseline": "PASS",
                "db_revision": fingerprint()["alembic_revision"],
                "rollback": ROLLBACK,
                "backup_bytes": len(backup),
            }
        )
    )
elif action == "build":
    with (PRIVATE / "build.log").open("w") as log:
        result = subprocess.run(
            ["docker", "build", "--target", "showcase", "-t", IMAGE, "."], stdout=log, stderr=log
        )
    image = (
        run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
        if not result.returncode
        else None
    )
    save(
        "build.json",
        {
            "exit": result.returncode,
            "image": IMAGE,
            "image_id": image,
            "log": str(PRIVATE / "build.log"),
        },
    )
    print(json.dumps({"build_exit": result.returncode, "image_id": image}))
    raise SystemExit(result.returncode)
elif action == "upgrade":
    assert (
        json.loads((EVIDENCE / "before-data.json").read_text()) == fingerprint()
    ), "Data changed since baseline; inspect before upgrade"
    output = compose(PRIVATE / "upgrade.json", "up", "-d", "--no-deps", "--no-build", "api")
    (PRIVATE / "upgrade.log").write_text(output)
    healthy = False
    for _ in range(45):
        row = status()[0]
        if row["health"] == "healthy":
            healthy = True
            break
        time.sleep(2)
    unchanged = json.loads((EVIDENCE / "before-data.json").read_text()) == fingerprint()
    if not healthy or not unchanged:
        compose(PRIVATE / "rollback.json", "up", "-d", "--no-deps", "--no-build", "api")
        raise RuntimeError("Upgrade failed health/preservation; previous API image restored")
    save(
        "after-upgrade.json",
        {"healthy": healthy, "database_byte_fingerprints_unchanged": unchanged, "status": status()},
    )
    print(
        json.dumps(
            {
                "upgrade": "PASS",
                "database_byte_fingerprints_unchanged": unchanged,
                "status": status(),
            }
        )
    )
elif action == "discover":
    print(
        run(
            "find",
            "/home/panda/.cache",
            "/home/panda/.local",
            "/opt",
            "-maxdepth",
            "5",
            "-name",
            "python",
            "-o",
            "-name",
            "chrome",
            "-o",
            "-name",
            "node",
        )
    )
elif action == "browser-path":
    source = Path("/home/panda/.local/state/adaptive-rag-production-20261113/browser-config.json")
    destination = Path("/home/panda/.local/adaptive-rag-production-20261113")
    destination.mkdir(mode=0o700)
    os.chown(destination, 1000, 1000)
    source.rename(destination / "browser-config.json")
    print("BROWSER_CONFIG_ACCESS_FIXED; mode0600 unchanged; no token output")
