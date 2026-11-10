"""Explicit, private, loopback-only Ubuntu sandbox. Never discover production DSNs."""

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import socket
import subprocess
from pathlib import Path

from .manage import HERE, save, sha

COMPOSE = HERE / "compose.integration.yml"
SERVICES = {"postgres", "redis", "qdrant"}


def project_check(project):
    if not isinstance(project, str) or not re.fullmatch(r"p4b_[a-z0-9_]{3,40}", project):
        raise ValueError("invalid isolated project")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def prepare(parent, project, *, ports=None):
    project_check(project)
    ports = ports or tuple(free_port() for _ in range(3))
    if len(set(ports)) != 3 or any(type(p) is not int or not 1024 <= p <= 65535 for p in ports):
        raise ValueError("three unique nonprivileged ports required")
    directory = Path(parent).resolve() / project
    directory.mkdir(parents=True, exist_ok=False)
    password = secrets.token_urlsafe(36)
    owner = secrets.token_hex(16)
    pg, rd, qd = ports
    cfg = dict(
        version=1,
        project=project,
        owner=owner,
        password=password,
        pg_port=pg,
        redis_port=rd,
        qdrant_port=qd,
        database_url=f"postgresql+asyncpg://p4b:{password}@127.0.0.1:{pg}/{project}",
        redis_url=f"redis://127.0.0.1:{rd}/13",
        qdrant_url=f"http://127.0.0.1:{qd}",
        collection=project,
        compose_sha256=sha(COMPOSE),
    )
    path = directory / "manifest.json"
    save(path, cfg)
    env = directory / "compose.env"
    env.write_text(
        f"PROJECT={project}\nOWNER={owner}\nPG_PASSWORD={password}\nPG_PORT={pg}\nREDIS_PORT={rd}\nQDRANT_PORT={qd}\n",
        encoding="utf8",
    )
    for item in (path, env):
        os.chmod(item, 0o600)
    save(
        directory / "public.json",
        dict(
            project=project,
            owner_sha256=hashlib.sha256(owner.encode()).hexdigest(),
            ports=list(ports),
            compose_sha256=sha(COMPOSE),
            paid_calls=0,
            experience_active=False,
        ),
    )
    return path


def load(path):
    path = Path(path).resolve(strict=True)
    cfg = json.loads(path.read_bytes())
    project_check(cfg["project"])
    p = cfg["project"]
    password = cfg["password"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{48}", password) or not re.fullmatch(
        r"[a-f0-9]{32}", cfg["owner"]
    ):
        raise ValueError("invalid private credentials")
    ports = [cfg[k] for k in ("pg_port", "redis_port", "qdrant_port")]
    if len(set(ports)) != 3 or any(type(n) is not int or not 1024 <= n <= 65535 for n in ports):
        raise ValueError("invalid port allocation")
    expected = dict(
        database_url=f"postgresql+asyncpg://p4b:{password}@127.0.0.1:{ports[0]}/{p}",
        redis_url=f"redis://127.0.0.1:{ports[1]}/13",
        qdrant_url=f"http://127.0.0.1:{ports[2]}",
        collection=p,
        compose_sha256=sha(COMPOSE),
        version=1,
    )
    if any(cfg.get(k) != v for k, v in expected.items()):
        raise ValueError("manifest target or compose changed")
    return cfg


def live_config():
    if platform.system() != "Linux" or os.environ.get("P4B_RUN_LIVE") != "1":
        raise RuntimeError("real services require explicit Ubuntu P4B_RUN_LIVE=1")
    path = Path(os.environ["P4B_MANIFEST"]).resolve(strict=True)
    if not path.is_relative_to((HERE / ".private").resolve()):
        raise ValueError("private manifest must belong to this phase")
    return path, load(path)


def command(path, action, service=None):
    """Mutations require owned resources. Stop retains volumes; no prune/down command."""
    live_path, cfg = live_config()
    if Path(path).resolve() != live_path or action not in {"up", "ps", "stop", "start", "restart"}:
        raise ValueError("unsupported sandbox operation")
    if service is not None and service not in SERVICES:
        raise ValueError("unknown service")
    docker = ["docker", "--host", "unix:///var/run/docker.sock"]
    # Neither host interpolation variables nor an ambient remote Docker context may
    # redirect an operation away from the checked local sandbox.
    child_env = {
        k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LD_LIBRARY_PATH"}
    }
    base = docker + [
        "compose",
        "-p",
        cfg["project"],
        "-f",
        str(COMPOSE),
        "--env-file",
        str(live_path.parent / "compose.env"),
    ]
    # Do not trust editable env-file targets: rewrite only from the validated manifest.
    env_path = live_path.parent / "compose.env"
    expected = f"PROJECT={cfg['project']}\nOWNER={cfg['owner']}\nPG_PASSWORD={cfg['password']}\nPG_PORT={cfg['pg_port']}\nREDIS_PORT={cfg['redis_port']}\nQDRANT_PORT={cfg['qdrant_port']}\n"
    if env_path.read_text(encoding="utf8") != expected:
        raise ValueError("private env changed")
    ids = (
        subprocess.check_output(
            docker
            + ["ps", "-aq", "--filter", f"label=com.docker.compose.project={cfg['project']}"],
            env=child_env,
        )
        .decode()
        .split()
    )
    seen = set()
    expected_ports = {
        "postgres": ("5432/tcp", cfg["pg_port"], "pgdata"),
        "redis": ("6379/tcp", cfg["redis_port"], "redisdata"),
        "qdrant": ("6333/tcp", cfg["qdrant_port"], "qdrantdata"),
    }
    for resource in ids:
        info = json.loads(subprocess.check_output(docker + ["inspect", resource], env=child_env))[0]
        labels = info["Config"].get("Labels", {})
        if (
            labels.get("p4b.owner") != cfg["owner"]
            or labels.get("com.docker.compose.project") != cfg["project"]
        ):
            raise ValueError("existing project not owned; choose a new project")
        role = labels.get("com.docker.compose.service")
        if role not in SERVICES or role in seen:
            raise ValueError("unknown or duplicate owned service")
        seen.add(role)
        internal, external, volume_suffix = expected_ports[role]
        binding = [{"HostIp": "127.0.0.1", "HostPort": str(external)}]
        if info.get("HostConfig", {}).get("PortBindings", {}).get(internal) != binding:
            raise ValueError("container port binding does not match private manifest")
        if not any(
            m.get("Name") == cfg["project"] + "_" + volume_suffix for m in info.get("Mounts", [])
        ):
            raise ValueError("unexpected container data volume")
        if action == "ps" and (
            not info.get("State", {}).get("Running")
            or info.get("NetworkSettings", {}).get("Ports", {}).get(internal) != binding
        ):
            raise ValueError("owned endpoint is not running on the expected loopback port")
    if action == "ps" and seen != SERVICES:
        raise ValueError("all three owned service endpoints are required")
    # Compose's deterministic volume names can collide with an unlabeled user
    # volume even when there are no project-labeled containers/volumes.
    names = (
        subprocess.check_output(docker + ["volume", "ls", "--format", "{{.Name}}"], env=child_env)
        .decode()
        .split()
    )
    for suffix in ("pgdata", "redisdata", "qdrantdata"):
        name = cfg["project"] + "_" + suffix
        if name in names:
            volume = json.loads(
                subprocess.check_output(docker + ["volume", "inspect", name], env=child_env)
            )[0]
            labels = volume.get("Labels") or {}
            if (
                labels.get("p4b.owner") != cfg["owner"]
                or labels.get("com.docker.compose.project") != cfg["project"]
            ):
                raise ValueError("existing volume not owned; choose a new project")
    if not ids and action != "up":
        raise ValueError("owned services absent")
    if action == "up" and not ids:
        # Existing volumes must never be silently adopted.
        volumes = (
            subprocess.check_output(
                docker
                + [
                    "volume",
                    "ls",
                    "-q",
                    "--filter",
                    f"label=com.docker.compose.project={cfg['project']}",
                ],
                env=child_env,
            )
            .decode()
            .split()
        )
        if volumes:
            raise ValueError(
                "existing project volumes; choose a new project or audit ownership manually"
            )
    args = [action] + (["-d", "--wait", "--wait-timeout", "120"] if action == "up" else [])
    if service:
        args.append(service)
    subprocess.run(base + args, check=True, timeout=180, stdout=subprocess.DEVNULL, env=child_env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "up", "ps", "stop", "start", "restart"])
    parser.add_argument("--project")
    parser.add_argument("--service", choices=sorted(SERVICES))
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare(HERE / ".private", args.project))
    else:
        manifest, _ = live_config()
        command(manifest, args.action, args.service)
