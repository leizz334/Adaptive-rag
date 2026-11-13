"""Final read-only evidence and explicitly authorized owned-test cleanup."""

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
EVIDENCE = HERE / "evidence"
PRIVATE = Path("/root/.local/state/adaptive-rag-production-20261113")
os.umask(0o077)


def run(*args, data=None):
    result = subprocess.run(args, input=data, capture_output=True, check=True)
    return result.stdout


def save(name, value):
    with (EVIDENCE / name).open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)


def containers():
    ids = run("docker", "ps", "-aq").decode().split()
    return json.loads(run("docker", "inspect", *ids)) if ids else []


def volumes():
    return sorted(run("docker", "volume", "ls", "--format", "{{.Name}}").decode().splitlines())


if sys.argv[1] == "verify":
    code = """
import json,hashlib
from pathlib import Path
from app.demo.docker import runtime_settings
from app.experience.settings import ExperienceSettings
s=runtime_settings()
print(json.dumps({'app_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('app').rglob('*.py')},'experience_mode':ExperienceSettings().experience_memory_mode,'paid_key_present':bool(s.deepseek_api_key.get_secret_value())}))
"""
    runtime = json.loads(run("docker", "exec", "adaptive-rag-showcase-api-1", "python", "-c", code))
    local = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "app").rglob("*.py")
    }
    assert runtime["app_hashes"] == local
    assert str(runtime["experience_mode"]).lower() == "off" and not runtime["paid_key_present"]
    cfg = json.loads(
        run(
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "-p",
            "adaptive-rag-showcase",
            "-f",
            str(ROOT / "compose.showcase.yml"),
            "-f",
            str(HERE / "compose.production.yml"),
            "config",
            "--format",
            "json",
        )
    )
    assert cfg["services"]["api"]["image"] == "adaptive-rag-production:be2931f-20261113"
    assert cfg["services"]["api"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 8000,
            "published": "8000",
            "protocol": "tcp",
        }
    ]
    # Compare pre-existing rows from the private backup without restoring any DB.
    dump = run(
        "docker",
        "exec",
        "-i",
        "adaptive-rag-showcase-postgres-1",
        "pg_restore",
        "--data-only",
        "--file=-",
        data=(PRIVATE / "postgres-before.dump").read_bytes(),
    ).decode()
    old_tables = {}
    table = None
    for line in dump.splitlines():
        match = re.fullmatch(r"COPY public\.(\w+) \((.+)\) FROM stdin;", line)
        if match:
            table = match.group(1)
            old_tables[table] = {"columns": match.group(2), "rows": []}
        elif table and line == r"\.":
            table = None
        elif table:
            old_tables[table]["rows"].append(line)
    assert old_tables, "Backup COPY sections must be present"
    checks = {}
    allowed_order_changes = []
    allowed_generation_changes = []
    for table, value in old_tables.items():
        assert table.replace("_", "").isalnum()
        query = 'COPY public."' + table + '" (' + value["columns"] + ") TO STDOUT"
        current = (
            run(
                "docker",
                "exec",
                "adaptive-rag-showcase-postgres-1",
                "psql",
                "-U",
                "adaptive",
                "-d",
                "adaptive_showcase",
                "-Atc",
                query,
            )
            .decode()
            .splitlines()
        )
        missing = Counter(value["rows"]) - Counter(current)
        if table == "orders":
            for row in list(missing):
                fields = row.split("\t")
                if fields[0] in {"ORD95102", "ORD95107"}:
                    changed = fields.copy()
                    changed[2] = "cancelled"
                    assert "\t".join(changed) in current and fields[2] == "paid"
                    allowed_order_changes.append(fields[0])
                    del missing[row]
        if table == "private_knowledge_tenants":
            for row in list(missing):
                fields = row.split("\t")
                match = next(
                    (r.split("\t") for r in current if r.split("\t")[0] == fields[0]), None
                )
                if fields[0] in {"web_demo_a", "web_demo_b"} and match is not None:
                    assert len(fields) == len(match) == 2 and int(match[1]) > int(fields[1])
                    allowed_generation_changes.append(
                        {"subject": fields[0], "before": int(fields[1]), "after": int(match[1])}
                    )
                    del missing[row]
        if missing:
            columns = value["columns"].split(", ")
            comparisons = []
            for row in missing:
                fields = row.split("\t")
                match = next(
                    (r.split("\t") for r in current if r.split("\t")[0] == fields[0]), None
                )
                comparisons.append(
                    {
                        "row_present": match is not None,
                        "changed_columns": [
                            c
                            for c, a, b in zip(columns, fields, match or [], strict=False)
                            if a != b
                        ],
                    }
                )
            print(
                json.dumps(
                    {
                        "preservation_mismatch_table": table,
                        "missing_count": len(missing),
                        "comparisons": comparisons,
                    }
                )
            )
        assert not missing, (
            "Pre-existing database rows changed outside authorized synthetic order transitions: "
            + table
        )
        checks[table] = {
            "original_rows": len(value["rows"]),
            "current_rows": len(current),
            "preserved": True,
        }
    before = json.loads((EVIDENCE / "before-containers.json").read_text())
    rows = containers()
    for old in before:
        if old["project"] == "adaptive-rag-showcase" and old["service"] in [
            "postgres",
            "redis",
            "qdrant",
        ]:
            actual = next(row for row in rows if row["Id"] == old["id"])
            assert actual["State"]["Health"]["Status"] == "healthy"
            assert sorted(m.get("Name") for m in actual["Mounts"]) == sorted(
                m.get("Name") for m in old["mounts"]
            )
    save(
        "final-data-verification.json",
        {
            "app_python_files_match": len(local),
            "experience_mode": "off",
            "paid_key_present": False,
            "production_overlay_valid": True,
            "preexisting_rows": checks,
            "authorized_synthetic_status_changes": allowed_order_changes,
            "authorized_test_kb_generation_changes": allowed_generation_changes,
            "database_containers_and_mounts_preserved": True,
        },
    )
    save("volumes-before-cleanup.json", volumes())
    print(
        json.dumps(
            {
                "source_matches": len(local),
                "existing_rows_preserved": True,
                "synthetic_changes": allowed_order_changes,
                "volumes": len(volumes()),
            }
        )
    )
elif sys.argv[1] == "cleanup":
    tasks = json.loads((HERE / "feature-list.json").read_text())["tasks"]
    assert all(task["passes"] for task in tasks if task["id"] in ["W1", "W2", "W3", "W4"])
    assert not any(
        ":18083" in line for line in run("ss", "-tn", "state", "established").decode().splitlines()
    ), "Old workbench still has established clients"
    project = "adaptive-rag-w1-20261113"
    old = [
        row
        for row in containers()
        if row["Config"]["Labels"].get("com.docker.compose.project") == project
    ]
    assert len(old) == 6 and {
        row["Config"]["Labels"].get("com.docker.compose.service") for row in old
    } == {"api", "postgres", "redis", "qdrant", "bootstrap", "initialize"}
    active = (
        run(
            "docker",
            "exec",
            project + "-postgres-1",
            "psql",
            "-U",
            "adaptive",
            "-d",
            "adaptive_showcase",
            "-Atc",
            "SELECT count(*) FROM pg_stat_activity WHERE datname='adaptive_showcase' AND state='active' AND pid<>pg_backend_pid()",
        )
        .decode()
        .strip()
    )
    assert active == "0", "Old workbench database has active operations"
    for row in old:
        assert row["Config"]["Labels"].get("io.adaptive-rag.showcase") == "s1-docker-v1"
        assert all(m.get("Name", "").startswith(project + "_") for m in row["Mounts"])
    previous_volumes = volumes()
    assert previous_volumes == json.loads((EVIDENCE / "volumes-before-cleanup.json").read_text())
    running = [r["Id"] for r in old if r["State"]["Running"]]
    if running:
        run("docker", "stop", *running)
    run("docker", "rm", *[row["Id"] for row in old])
    assert volumes() == previous_volumes
    remaining = containers()
    running = [r for r in remaining if r["State"]["Running"]]
    assert len(running) == 4 and all(
        r["Config"]["Labels"].get("com.docker.compose.project") == "adaptive-rag-showcase"
        for r in running
    )
    assert all(
        not r["State"]["Running"]
        for r in remaining
        if r["Config"]["Labels"].get("com.docker.compose.project") == "p4b_ww_w4_20261113_01"
    )
    save(
        "cleanup.json",
        {
            "removed_container_names": [r["Name"] for r in old],
            "old_workbench_active_db_operations": 0,
            "old_workbench_established_clients": 0,
            "remaining_running": [
                {
                    "name": r["Name"],
                    "image": r["Image"],
                    "health": r["State"].get("Health", {}).get("Status"),
                }
                for r in running
            ],
            "all_volumes_preserved": volumes(),
            "volume_count": len(volumes()),
            "p4b_stopped": True,
            "real_dev_running": False,
        },
    )
    print(
        json.dumps(
            {
                "running": len(running),
                "removed_test_containers": len(old),
                "volumes_retained": len(volumes()),
                "real_dev_running": False,
            }
        )
    )
