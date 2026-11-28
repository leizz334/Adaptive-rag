"""Run final PostgreSQL engineering tests from a clean Git archive."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import asyncpg

SANDBOX = "adaptive_rag_final_engineering"
TEST_PATH = Path("tests/integration/test_final_postgres.py")


def source_env(port):
    """Pass system paths and the disposable DSN, without application credentials."""
    keep = {
        "path",
        "pathext",
        "systemroot",
        "windir",
        "temp",
        "tmp",
        "comspec",
        "lang",
        "appdata",
        "localappdata",
        "userprofile",
    }
    env = {key: value for key, value in os.environ.items() if key.casefold() in keep}
    env["PYTHONUTF8"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["ADAPTIVE_RAG_FINAL_PG_URL"] = (
        f"postgresql+asyncpg://adaptive_rag_final@127.0.0.1:{port}/{SANDBOX}"
    )
    return env


async def migrate(port, sql, expected_revision):
    connection = await asyncpg.connect(
        host="127.0.0.1", port=port, user="adaptive_rag_final", database=SANDBOX, timeout=3
    )
    try:
        assert await connection.fetchval("SHOW cluster_name") == SANDBOX
        assert await connection.fetchval("SELECT current_database()") == SANDBOX
        assert await connection.fetchval("SHOW listen_addresses") == "127.0.0.1"
        version = await connection.fetchval("SHOW server_version")
        if await connection.fetchval("SELECT to_regclass('public.alembic_version')"):
            applied = "already_applied"
        else:
            assert (
                await connection.fetchval(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
                )
                == 0
            ), "migration requires a pristine disposable database"
            await connection.execute(sql)
            applied = "applied"
        revision = await connection.fetchval("SELECT version_num FROM alembic_version")
        assert revision == expected_revision, (revision, expected_revision)
        return {"server_version": version, "alembic_revision": revision, "migration": applied}
    finally:
        await connection.close()


def run(args):
    repo = args.repo.resolve()
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{args.ref}^{{commit}}"], cwd=repo, text=True
    ).strip()
    fixture = (repo / TEST_PATH).read_bytes()
    env = source_env(args.port)
    with tempfile.TemporaryDirectory(prefix="adaptive-rag-engineering-") as scratch:
        path = Path(scratch)
        archive = path / "source.zip"
        subprocess.run(
            ["git", "archive", "--format=zip", "--output", str(archive), commit],
            cwd=repo,
            check=True,
        )
        source = path / "source"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(source)
        archived_fixture = source / TEST_PATH
        fixture_origin = "commit"
        if not archived_fixture.exists():
            archived_fixture.write_bytes(fixture)
            fixture_origin = "engineering_fixture_overlay"
        assert not (source / ".env").exists()
        fixture_hash = hashlib.sha256(archived_fixture.read_bytes()).hexdigest()

        dependencies = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        migration = subprocess.run(
            [
                sys.executable,
                "-c",
                "\n".join(
                    (
                        "import sys",
                        "from alembic.command import upgrade",
                        "from alembic.config import Config",
                        "from alembic.script import ScriptDirectory",
                        "config = Config('alembic.ini')",
                        "config.set_main_option('sqlalchemy.url', 'postgresql://')",
                        "print(ScriptDirectory.from_config(config).get_current_head(), file=sys.stderr)",
                        "upgrade(config, 'head', sql=True)",
                    )
                ),
            ],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        expected_revision = migration.stderr.splitlines()[0]
        postgres = asyncio.run(migrate(args.port, migration.stdout, expected_revision))
        test_result = path / "pytest.xml"
        tests = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "pytest_asyncio.plugin",
                "-vv",
                "--tb=short",
                f"--junitxml={test_result}",
                TEST_PATH.as_posix(),
            ],
            cwd=source,
            env=env,
            text=True,
            capture_output=True,
            encoding="utf-8",
        )
        stdout = tests.stdout.replace(str(path), "<git-archive>").replace(
            sys.prefix, "<conda-adaptive-rag>"
        )
        stderr = tests.stderr.replace(str(path), "<git-archive>").replace(
            sys.prefix, "<conda-adaptive-rag>"
        )
        print(stdout, end="")
        if stderr:
            print(stderr, end="", file=sys.stderr)
        # The opt-in contract must actually exercise a live database in this runner.
        result = ElementTree.parse(test_result).find("testsuite")
        assert result is not None
        counts = {
            key: int(result.attrib[key]) for key in ("tests", "failures", "errors", "skipped")
        }
        exit_code = tests.returncode or int(not counts["tests"] or counts["skipped"] > 0)
        evidence = {
            "source_commit": commit,
            "fixture_origin": fixture_origin,
            "fixture_sha256": fixture_hash,
            "python_version": sys.version.split()[0],
            "packages": {
                package: importlib.metadata.version(package)
                for package in (
                    "alembic",
                    "asyncpg",
                    "fastapi",
                    "httpx",
                    "pytest",
                    "sqlalchemy",
                    "sse-starlette",
                    "uvicorn",
                )
            },
            "pip_check": dependencies.stdout.strip(),
            "postgres": postgres,
            "test_counts": counts,
            "tests_exit_code": exit_code,
            "tests_output": stdout,
        }
        if args.evidence:
            args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--ref", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("the sandbox requires a non-privileged loopback port")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
