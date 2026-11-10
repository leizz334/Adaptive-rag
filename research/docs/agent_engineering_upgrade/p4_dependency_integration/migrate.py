"""Explicit owned Ubuntu database migrations, never ambient alembic.ini URL."""

import argparse
import asyncio
import json

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from alembic.config import Config

from .manage import ROOT, save
from .sandbox import command as owned_command, live_config


async def table_names(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(lambda c: inspect(c).get_table_names())
    finally:
        await engine.dispose()


def roundtrip_allowed(path, cfg, names):
    """Never repeat a destructive initial acceptance operation on resumed data."""
    marker = path.parent / "migration_roundtrip.json"
    expected = dict(project=cfg["project"], compose_sha256=cfg["compose_sha256"])
    if marker.exists():
        if json.loads(marker.read_bytes()) != expected:
            raise ValueError("migration marker mismatch")
        return False
    if names:
        raise ValueError(
            "roundtrip requires a fresh empty owned database; preserve current data and choose new project"
        )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help="Private initial B2 schema only, no API processes may be running",
    )
    args = parser.parse_args()
    path, cfg = live_config()
    owned_command(path, "ps")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", cfg["database_url"])
    initial = args.roundtrip and roundtrip_allowed(
        path, cfg, asyncio.run(table_names(cfg["database_url"]))
    )
    command.upgrade(config, "head")
    if initial:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        save(
            path.parent / "migration_roundtrip.json",
            dict(project=cfg["project"], compose_sha256=cfg["compose_sha256"]),
        )


if __name__ == "__main__":
    main()
