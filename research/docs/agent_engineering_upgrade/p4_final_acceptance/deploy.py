"""Loopback-only deployment demo using the actual ASGI app and owned dependencies.

This is a no-paid offline deployment profile, not a production authentication issuer.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    free_port,
    live_config,
)


def private_api_config(manifest):
    path = manifest.parent / "p4e_api.private.json"
    if not path.exists():
        token = secrets.token_urlsafe(36)
        data = {
            "port": free_port(),
            "token": token,
            "credentials": json.dumps(
                {
                    "version": 1,
                    "credentials": [
                        {
                            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                            "subject": "p4e_deploy_demo",
                            "roles": ["user"],
                            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                            "revoked": False,
                        }
                    ],
                }
            ),
        }
        # Restrict permissions at creation, before any plaintext token is written.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
    return json.loads(path.read_text())


def environment(cfg, api):
    env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LD_LIBRARY_PATH"}}
    env.update(
        APP_ENV="production",
        LOG_LEVEL="INFO",
        KNOWLEDGE_DIR=str(Path(__file__).resolve().parents[4] / "knowledge"),
        ADMIN_API_TOKEN="",
        AUTH_MODE="required",
        AUTH_CREDENTIALS=api["credentials"],
        DATABASE_URL=cfg["database_url"],
        REDIS_URL=cfg["redis_url"],
        QDRANT_URL=cfg["qdrant_url"],
        QDRANT_COLLECTION=cfg["collection"] + "_deploy_public",
        LOCAL_EMBEDDING_ENABLED="false",
        CROSS_ENCODER_ENABLED="false",
        UNSTRUCTURED_ENABLED="false",
        DEEPSEEK_API_KEY="",
        EMBEDDING_API_KEY="",
        EXPERIENCE_MEMORY_MODE="off",
        LANGSMITH_API_KEY="",
        AGENT_LANGSMITH_API_KEY="",
        AGENT_TRACING_ENABLED="false",
        MCP_ENABLED="false",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PYTHONPATH=str(Path(__file__).resolve().parents[4]),
    )
    return env


def argv(api):
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.asgi:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api["port"]),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["serve", "info"])
    args = parser.parse_args()
    manifest, cfg = live_config()
    command(manifest, "ps")
    api = private_api_config(manifest)
    if args.action == "info":
        print(
            json.dumps(
                {
                    "url": f"http://127.0.0.1:{api['port']}",
                    "private_credentials_file": str(manifest.parent / "p4e_api.private.json"),
                    "profile": "OFFLINE_DEMO_NOT_PRODUCTION",
                    "paid_requests": 0,
                    "active": False,
                }
            )
        )
    else:
        subprocess.run(argv(api), env=environment(cfg, api), check=True)


if __name__ == "__main__":
    main()
