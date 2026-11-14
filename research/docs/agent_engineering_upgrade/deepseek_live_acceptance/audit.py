"""D1 safe diagnostics: never emits secrets or calls model completions."""

import hashlib
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_live_acceptance"
OUT = HERE / "evidence"
OUT.mkdir(parents=True, exist_ok=True)


def probe():
    started = time.monotonic()
    result = {}
    try:
        result["dns_addresses"] = len(
            socket.getaddrinfo("api.deepseek.com", 443, type=socket.SOCK_STREAM)
        )
        with socket.create_connection(("api.deepseek.com", 443), timeout=8) as sock:
            with ssl.create_default_context().wrap_socket(
                sock, server_hostname="api.deepseek.com"
            ) as tls:
                result.update(tls_verified=True, tls_version=tls.version())
    except Exception as exc:
        result.update(tls_verified=False, error_type=type(exc).__name__)
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    return result


if sys.argv[1] == "snapshot":
    env_file = ROOT / ".env"
    cfg = dotenv_values(env_file, encoding="utf-8-sig") if env_file.is_file() else {}
    key = cfg.get("DEEPSEEK_API_KEY") or ""
    model = cfg.get("DEEPSEEK_MODEL") or "deepseek-chat"
    url = urlsplit(cfg.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com")
    ids = subprocess.check_output(["docker", "ps", "-aq"], text=True).split()
    rows = json.loads(subprocess.check_output(["docker", "inspect", *ids]))
    containers = [
        {
            "id": r["Id"],
            "name": r["Name"],
            "image": r["Image"],
            "state": r["State"]["Status"],
            "started": r["State"]["StartedAt"],
            "project": r["Config"]["Labels"].get("com.docker.compose.project"),
            "mounts": [m.get("Name") for m in r["Mounts"]],
        }
        for r in rows
    ]
    result = {
        "env_exists": env_file.is_file(),
        "env_sha256": hashlib.sha256(env_file.read_bytes()).hexdigest(),
        "key_configured_nonempty": bool(key.strip()),
        "model": model
        if model.startswith("deepseek-") and len(model) < 64
        else "NON_STANDARD_REDACTED",
        "base_url_official": url.scheme == "https" and url.hostname == "api.deepseek.com",
        "base_path_supported": url.path.rstrip("/") in ["", "/v1"],
        "proxy_variable_names": [name for name in os.environ if name.lower().endswith("_proxy")],
        "wsl_direct_network": probe(),
        "containers": containers,
        "model_http_requests": 0,
    }
    with (OUT / "D1-baseline.json").open("x") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "containers"}))
elif sys.argv[1] == "probe":
    print(json.dumps(probe()))
