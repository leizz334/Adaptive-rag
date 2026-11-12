"""Loopback-only, no-paid Web demos using owned real dependencies and synthetic orders."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    free_port,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_final_acceptance.deploy import environment

HERE = Path(__file__).resolve().parent
PRIVATE = HERE / ".private"
API = PRIVATE / "demo_api.json"


def config():
    manifest, cfg = live_config()
    command(manifest, "ps")
    return manifest, cfg


async def seed(cfg):
    from app.demo.fixtures import seed as shared_seed

    await shared_seed(cfg)


def prepare():
    _, cfg = config()
    PRIVATE.mkdir(exist_ok=True)
    if not API.exists():
        tokens = {"a": secrets.token_urlsafe(36), "b": secrets.token_urlsafe(36)}
        rows = [
            {
                "token_sha256": hashlib.sha256(v.encode()).hexdigest(),
                "subject": f"web_demo_{k}",
                "roles": ["user"],
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            }
            for k, v in tokens.items()
        ]
        data = dict(
            port=free_port(),
            tokens=tokens,
            credentials=json.dumps(dict(version=1, credentials=rows)),
            project=cfg["project"],
        )
        fd = os.open(API, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
    if json.loads(API.read_text())["project"] != cfg["project"]:
        raise ValueError("private demo target mismatch")
    asyncio.run(seed(cfg))
    info()


def info():
    row = json.loads(API.read_text())
    print(
        json.dumps(
            dict(
                url=f"http://127.0.0.1:{row['port']}",
                private_credentials_file=str(API),
                model="CONTROLLED_OFFLINE_NOT_REAL_LLM",
                paid_requests=0,
                experience_active=False,
            )
        )
    )


def install_network_guard():
    """Deny non-loopback sockets even if a future demo accidentally selects a provider."""
    import socket

    original, original_ex = socket.socket.connect, socket.socket.connect_ex

    def check(address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise OSError("S1-Web demo forbids external network and paid dispatch")

    def connect(sock, address):
        check(address)
        return original(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_ex(sock, address)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex


def serve():
    install_network_guard()
    _, cfg = config()
    row = json.loads(API.read_text())
    if row["project"] != cfg["project"]:
        raise ValueError("private target mismatch")
    # Real environment values override any developer .env without modifying it.
    env = environment(cfg, row)
    env.update(
        KNOWLEDGE_MODE="private",
        RATE_LIMIT_PER_MINUTE="10000",
        AGENT_TRACING_ENABLED="true",
        AGENT_TRACING_BACKEND="local",
        MEMORY_MODE="M2",
        LOG_LEVEL="WARNING",
    )
    os.environ.update(env)
    from app.config.settings import Settings
    from app.main import create_app
    from app.services.container import build_container

    settings = Settings()
    if settings.llm_configured or settings.embedding_configured:
        raise RuntimeError("paid providers forbidden in web demo")
    app = create_app(settings)

    @asynccontextmanager
    async def lifespan(application):
        container = await build_container(settings, seed=False)
        try:
            if container.engine.dialect.name != "postgresql" or container.redis is None:
                raise RuntimeError("real dependencies required")
            if type(container.vector_store).__name__ != "PrivateVectorStore":
                raise RuntimeError("actual private Qdrant required")
            application.state.container = container
            yield
        finally:
            await container.aclose()

    app.router.lifespan_context = lifespan
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=row["port"], access_log=False, log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "serve", "info"])
    action = parser.parse_args().action
    {"prepare": prepare, "serve": serve, "info": info}[action]()
