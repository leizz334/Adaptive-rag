"""Owned W4 dependency preparation and explicit final-check runner (zero paid)."""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STATE = ROOT / "research/docs/agent_engineering_upgrade"
HERE = Path(__file__).resolve().parent
PROJECT = "p4b_ww_w4_20261113_01"
MANIFEST = STATE / f"p4_dependency_integration/.private/{PROJECT}/manifest.json"
EVIDENCE = HERE / "evidence/w4_backend_20261113_01"
RUN = "ww_w4_20261113_01"
PREFIX = "research.docs.agent_engineering_upgrade."
GIT_COMMON = Path("/mnt/d/Code/Adaptive-rag/.git")
GIT_OBJECTS = Path(
    "/mnt/c/Users/panda/.codex/recovery/"
    "Adaptive-rag-20261113-467df67775c0485fbcd23b50481ed14a.git/objects"
)


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def environment():
    env = os.environ.copy()
    env.update(
        P4B_RUN_LIVE="1",
        P4B_MANIFEST=str(MANIFEST),
        P4_E2E_RUN_ID=RUN + "_http",
        P4B_AUTH_RUN_ID=RUN + "_auth",
        P4B_API_RUN_ID=RUN + "_api",
        DEEPSEEK_API_KEY="",
        EMBEDDING_API_KEY="",
        EXPERIENCE_MEMORY_MODE="off",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONUTF8="1",
        # Windows absolute gitfile/commondir paths are not Linux paths. These
        # process-only overrides preserve all metadata and use the audited store.
        GIT_DIR=str(GIT_COMMON / "worktrees/p3-experience-validation"),
        GIT_COMMON_DIR=str(GIT_COMMON),
        GIT_WORK_TREE=str(ROOT),
        GIT_OBJECT_DIRECTORY=str(GIT_OBJECTS),
    )
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "check", "run", "stop"])
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ.update(environment())
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
        command,
        load,
        prepare,
    )

    assert GIT_OBJECTS.is_dir(), "Verified recovery object store is required"
    subprocess.run(["git", "rev-parse", "--verify", "HEAD"], env=environment(), check=True)
    if args.action == "prepare":
        if MANIFEST.exists() or EVIDENCE.exists():
            raise FileExistsError("Fresh W4 infrastructure already exists; use check")
        actual = prepare(MANIFEST.parent.parent, PROJECT)
        assert actual == MANIFEST
        command(MANIFEST, "up")
        with (MANIFEST.parent / "initial_migration.private.log").open("x") as log:
            subprocess.run(
                [sys.executable, "-m", PREFIX + "p4_dependency_integration.migrate", "--roundtrip"],
                check=True,
                stdout=log,
                stderr=log,
                env=environment(),
            )
        cfg = load(MANIFEST)
        marker = json.loads((MANIFEST.parent / "migration_roundtrip.json").read_bytes())
        assert marker == dict(project=PROJECT, compose_sha256=cfg["compose_sha256"])
        save_new(
            EVIDENCE / "infrastructure.json",
            dict(
                project=PROJECT,
                ports=[cfg[key] for key in ("pg_port", "redis_port", "qdrant_port")],
                migration_roundtrip="PASS_FRESH_EMPTY_OWNED_DB",
                paid_calls=0,
                experience_active=False,
                final_suite="NOT_RUN_WAITING_W3",
                volumes_retained=True,
            ),
        )
    elif args.action == "stop":
        command(MANIFEST, "stop")
        save_new(EVIDENCE / "stopped.json", dict(project=PROJECT, volumes_retained=True))
    elif args.action == "run":
        command(MANIFEST, "ps")
        runs = STATE / "p4_dependency_integration/runs"
        for name in (RUN + "_auth", RUN + "_api", RUN + "_legacy"):
            assert not (runs / name).exists(), "Never overwrite or reuse acceptance run IDs"
        assert not (STATE / "p4_api_e2e/runs" / (RUN + "_http")).exists()
        commands = {
            "pytest": [
                sys.executable,
                "-m",
                PREFIX + "p4_final_acceptance.offline",
                "pytest",
                "tests",
                "research/docs/agent_engineering_upgrade",
                "-q",
                "--junitxml=" + str(MANIFEST.parent / "pytest.private.xml"),
            ],
            "legacy214": [
                sys.executable,
                "-m",
                PREFIX + "p4_final_acceptance.offline",
                PREFIX + "p4_dependency_integration.regress",
                RUN + "_legacy",
            ],
            "ruff_check": [
                str(Path(sys.executable).parent / "ruff"),
                "check",
                "app",
                "tests",
                "eval",
                "alembic",
                "research",
                "scripts/showcase.py",
            ],
            "ruff_format": [
                str(Path(sys.executable).parent / "ruff"),
                "format",
                "--check",
                "app",
                "tests",
                "eval",
                "alembic",
                "research",
                "scripts/showcase.py",
            ],
            "mypy": [str(Path(sys.executable).parent / "mypy")],
            "pip_check": [sys.executable, "-m", "pip", "check"],
        }
        results = {}
        for name, argv in commands.items():
            with (MANIFEST.parent / (name + ".private.log")).open("x") as log:
                result = subprocess.run(argv, env=environment(), stdout=log, stderr=log)
            results[name] = dict(returncode=result.returncode, command=argv)
            if name == "pytest":
                junit = MANIFEST.parent / "pytest.private.xml"
                if junit.exists():
                    suites = ET.parse(junit).getroot().iter("testsuite")
                    results[name]["junit_summary"] = [
                        {key: value for key, value in suite.attrib.items() if key != "hostname"}
                        for suite in suites
                    ]
            save_new(EVIDENCE / (name + "_result.json"), results[name])
            print(name, result.returncode, flush=True)
        save_new(EVIDENCE / "checks.json", results)
        if any(row["returncode"] for row in results.values()):
            raise SystemExit(1)
    command(MANIFEST, "ps") if args.action != "stop" else None
    print(json.dumps(dict(action=args.action, project=PROJECT, paid_calls=0)))


if __name__ == "__main__":
    main()
