"""Fail-closed offline Compose showcase bootstrap and runtime."""

import argparse
import asyncio
import fcntl
import ipaddress
import json
import os
import re
import secrets
import socket
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.auth import Authenticator, mint_credential

SECRET_DIR = Path("/run/showcase-db")
STATE_DIR = Path("/var/lib/showcase")
CREDENTIAL_FILE = "development_credentials.json"


def _publish(path, data, mode):
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard link publishes atomically without replacing an existing record.
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _password(directory):
    path = directory / "postgres_password"
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid password state")
    value = path.read_text()
    if not re.fullmatch(r"[A-Za-z0-9_-]{64}", value):
        raise ValueError("invalid password state")
    return value


def read_credentials(directory=STATE_DIR):
    path = directory / CREDENTIAL_FILE
    if path.is_symlink() or not path.is_file():
        raise ValueError("invalid credential state")
    try:
        row = json.loads(path.read_text())
        if set(row) != {"version", "tokens", "credentials", "expires_at"} or row["version"] != 1:
            raise ValueError()
        expires = datetime.fromisoformat(row["expires_at"])
        if expires <= datetime.now(UTC) or set(row["tokens"]) != {"a", "b"}:
            raise ValueError()
        auth = Authenticator(row["credentials"])
        if len(auth.credentials) != 2:
            raise ValueError()
        for key in ("a", "b"):
            principal = auth.authenticate(["Bearer " + row["tokens"][key]])
            if principal.subject != "web_demo_" + key or principal.roles != {"user"}:
                raise ValueError()
        if any(c.expires_at != expires for c in auth.credentials):
            raise ValueError()
        return row
    except Exception:
        raise ValueError("invalid credential state") from None


def bootstrap(secret_dir=SECRET_DIR, state_dir=STATE_DIR, *, owner_uid=1000):
    for directory, mode in ((secret_dir, 0o755), (state_dir, 0o700)):
        if directory.is_symlink():
            raise ValueError("invalid state directory")
        directory.mkdir(parents=True, exist_ok=True, mode=mode)
        directory.chmod(mode)
    with (state_dir / ".bootstrap.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        password_path = secret_dir / "postgres_password"
        credential_path = state_dir / CREDENTIAL_FILE
        # Validate all existing state before creating any missing counterpart.
        if password_path.exists() or password_path.is_symlink():
            _password(secret_dir)
        if credential_path.exists() or credential_path.is_symlink():
            read_credentials(state_dir)
            if not password_path.exists():
                raise ValueError("inconsistent bootstrap volumes")
        if not password_path.exists():
            _publish(password_path, secrets.token_urlsafe(48), 0o444)
        if not credential_path.exists():
            expires = datetime.now(UTC) + timedelta(days=30)
            minted = {k: mint_credential("web_demo_" + k, expires, ["user"]) for k in ("a", "b")}
            row = dict(
                version=1,
                expires_at=expires.isoformat(),
                tokens={k: v["bearer_token"] for k, v in minted.items()},
                credentials=json.dumps(
                    dict(version=1, credentials=[v["registry_entry"] for v in minted.values()])
                ),
            )
            _publish(credential_path, json.dumps(row), 0o600)
        password_path.chmod(0o444)
        credential_path.chmod(0o600)
        if owner_uid is not None:
            for path in (state_dir, credential_path, Path(lock.name)):
                os.chown(path, owner_uid, owner_uid)


def runtime_settings(secret_dir=SECRET_DIR, state_dir=STATE_DIR, *, scrub_proxy=True):
    from app.config.settings import Settings

    # Explicit defaults for every field prevent host environment/dotenv overrides.
    values = {key: field.default for key, field in Settings.model_fields.items()}
    values.update(
        database_url=f"postgresql+asyncpg://adaptive:{_password(secret_dir)}@postgres:5432/adaptive_showcase",
        redis_url="redis://redis:6379/13",
        qdrant_url="http://qdrant:6333",
        auth_mode="required",
        auth_credentials=read_credentials(state_dir)["credentials"],
        app_env="production",
        knowledge_mode="private",
        memory_mode="M2",
        deepseek_api_key="",
        embedding_api_key="",
        admin_api_token="",
        agent_langsmith_api_key="",
        local_embedding_enabled=False,
        local_embedding_force=False,
        cross_encoder_enabled=False,
        cross_encoder_force=False,
        unstructured_enabled=False,
        unstructured_force=False,
        mcp_enabled=False,
        mcp_remote_url="",
        agent_tracing_enabled=True,
        agent_tracing_backend="local",
        log_level="WARNING",
        rate_limit_per_minute=10000,
    )
    for key in list(os.environ):
        if (scrub_proxy and key.lower().endswith("_proxy")) or key in {
            "LANGCHAIN_API_KEY",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_TRACING_V2",
            "LANGSMITH_TRACING",
        }:
            os.environ.pop(key, None)
    return Settings(_env_file=None, **values)


def network_allowlist():
    allowed = set()
    for host, port in [("postgres", 5432), ("redis", 6379), ("qdrant", 6333)]:
        for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            allowed.add((result[4][0], port))
    return allowed


def address_allowed(address, allowed):
    if not isinstance(address, tuple):
        return True  # Unix sockets
    host, port = address[:2]
    try:
        return ipaddress.ip_address(host).is_loopback or (host, port) in allowed
    except ValueError:
        return host == "localhost" or all(
            (r[4][0], port) in allowed
            for r in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        )


def install_network_guard():
    allowed = network_allowlist()
    original, original_ex = socket.socket.connect, socket.socket.connect_ex

    def connect(sock, address):
        if not address_allowed(address, allowed):
            raise OSError("showcase egress denied")
        return original(sock, address)

    def connect_ex(sock, address):
        if not address_allowed(address, allowed):
            raise OSError("showcase egress denied")
        return original_ex(sock, address)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex


async def initialize():
    install_network_guard()
    settings = runtime_settings()
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from alembic import command
    from alembic.config import Config
    from app.demo.fixtures import seed_session

    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(9510195201)"))

            def migrate(sync_connection):
                config = Config("alembic.ini")
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
            async with AsyncSession(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as db:
                async with db.begin():
                    await seed_session(db)
    finally:
        await engine.dispose()


def serve():
    install_network_guard()
    settings = runtime_settings()
    from contextlib import asynccontextmanager

    from app.main import create_app
    from app.services.container import build_container

    app = create_app(settings)

    @asynccontextmanager
    async def lifespan(application):
        container = await build_container(settings, seed=False)
        try:
            if (
                container.engine.dialect.name != "postgresql"
                or container.redis is None
                or type(container.vector_store).__name__ != "PrivateVectorStore"
            ):
                raise RuntimeError("required showcase backend unavailable")
            application.state.container = container
            yield
        finally:
            await container.aclose()

    app.router.lifespan_context = lifespan
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False, log_level="warning")


async def health():
    import httpx

    async with asyncio.timeout(4):
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:8000", timeout=1, trust_env=False
        ) as client:
            ready = (await client.get("/api/v1/ready")).json()
            dependencies = {d["name"]: d["ready"] for d in ready["dependencies"]}
            if not ready["ready"] or not all(
                dependencies.get(k) for k in ("database", "redis", "vector_store")
            ):
                raise RuntimeError("dependencies unavailable")
            caps = (await client.get("/api/v1/capabilities")).json()
            if any(
                caps.get(k) != v
                for k, v in {
                    "database": "postgresql",
                    "cache": "redis",
                    "llm": "offline",
                    "vector_store": "PrivateVectorStore",
                }.items()
            ):
                raise RuntimeError("unexpected backends")
            token = read_credentials()["tokens"]["a"]
            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
            )
            if response.status_code != 200 or response.json().get("subject") != "web_demo_a":
                raise RuntimeError("authentication unavailable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["bootstrap", "initialize", "serve", "health", "credentials"]
    )
    action = parser.parse_args().action
    try:
        if action == "bootstrap":
            bootstrap()
        elif action == "serve":
            serve()
        elif action == "credentials":
            read_credentials()
            print(STATE_DIR / CREDENTIAL_FILE)
        else:
            asyncio.run({"initialize": initialize, "health": health}[action]())
    except Exception as exc:
        print(type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
