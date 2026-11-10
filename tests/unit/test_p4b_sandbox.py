"""Windows checks of isolation controls; no real dependency service is claimed."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

MODULE = "research.docs.agent_engineering_upgrade.p4_dependency_integration"


def test_private_manifest_roundtrip_and_no_overwrite(tmp_path):
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
        load,
        prepare,
    )

    path = prepare(tmp_path, "p4b_unit_123", ports=(55432, 56379, 56333))
    cfg = load(path)
    assert cfg["project"] == "p4b_unit_123"
    assert cfg["database_url"].startswith("postgresql+asyncpg://p4b:")
    assert cfg["collection"] == "p4b_unit_123"
    assert cfg["redis_url"] == "redis://127.0.0.1:56379/13"
    assert "password" not in json.loads((path.parent / "public.json").read_text())
    with pytest.raises(FileExistsError):
        prepare(tmp_path, "p4b_unit_123", ports=(55432, 56379, 56333))


@pytest.mark.parametrize(
    "field,value",
    [
        ("project", "postgres"),
        ("database_url", "postgresql+asyncpg://p4b:x@production.example/p4b_unit_123"),
        ("database_url", "postgresql+asyncpg://p4b:x@127.0.0.1:55432/production"),
        ("redis_url", "redis://127.0.0.1:56379/0"),
        ("qdrant_url", "http://example.org:6333"),
        ("collection", "existing_user_collection"),
    ],
)
def test_manifest_tampering_rejected(tmp_path, field, value):
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
        load,
        prepare,
    )

    path = prepare(tmp_path, "p4b_unit_123", ports=(55432, 56379, 56333))
    cfg = json.loads(path.read_text())
    cfg[field] = value
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load(path)


@pytest.mark.parametrize("project", ["default", "p4b_../x", "p4b_UPPER", "p4b_x;rm", "p4b_"])
def test_unsafe_project_rejected(tmp_path, project):
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import prepare

    with pytest.raises(ValueError):
        prepare(tmp_path, project, ports=(55432, 56379, 56333))


def test_async_alembic_upgrade_downgrade(tmp_path):
    """Actual migration RED: async SQLite URL fails in the old sync-only env.py."""
    root = Path(__file__).resolve().parents[2]
    script = tmp_path / "migrate.py"
    script.write_text(
        "from alembic.config import Config\nfrom alembic import command\n"
        "import sys\nc=Config('alembic.ini')\n"
        "c.set_main_option('sqlalchemy.url',sys.argv[1])\n"
        "command.upgrade(c,'head')\ncommand.downgrade(c,'base')\ncommand.upgrade(c,'head')\n"
    )
    done = subprocess.run(
        [
            sys.executable,
            str(script),
            f"sqlite+aiosqlite:///{(tmp_path / 'migration.db').as_posix()}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
