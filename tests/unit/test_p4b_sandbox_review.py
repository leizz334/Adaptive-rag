"""Offline ownership counterexamples; no Docker executable or services run."""

import json
import subprocess

import pytest

from research.docs.agent_engineering_upgrade.p4_dependency_integration import migrate, sandbox


class Prepared:
    """Keep generated scratch credentials out of pytest's fixture traceback."""

    def __init__(self, path, cfg):
        self.path = path
        self.cfg = cfg

    def __iter__(self):
        return iter((self.path, self.cfg))

    def __repr__(self):
        return "<isolated synthetic scratch configuration>"


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    path = sandbox.prepare(tmp_path, "p4b_review", ports=(15432, 16379, 16333))
    cfg = sandbox.load(path)
    monkeypatch.setattr(sandbox, "live_config", lambda: (path, cfg))
    return Prepared(path, cfg)


def _docker(
    monkeypatch, cfg, *, owned_container=False, foreign_volume=False, complete=False, damage=None
):
    runs = []

    def output(args, **kwargs):
        if args[:3] == ["docker", "--host", "unix:///var/run/docker.sock"]:
            args = ["docker"] + args[3:]
        if args[:3] == ["docker", "ps", "-aq"]:
            if complete:
                return b"postgres redis qdrant\n"
            return b"owned-container\n" if owned_container else b""
        if args[:2] == ["docker", "inspect"]:
            role = args[-1] if complete else "redis"
            inside, outside, suffix = {
                "postgres": ("5432/tcp", cfg["pg_port"], "pgdata"),
                "redis": ("6379/tcp", cfg["redis_port"], "redisdata"),
                "qdrant": ("6333/tcp", cfg["qdrant_port"], "qdrantdata"),
            }[role]
            binding = [{"HostIp": "127.0.0.1", "HostPort": str(outside)}]
            info = {
                "Config": {
                    "Labels": {
                        "p4b.owner": cfg["owner"],
                        "com.docker.compose.project": cfg["project"],
                        "com.docker.compose.service": role,
                    }
                },
                "HostConfig": {"PortBindings": {inside: binding}},
                "NetworkSettings": {"Ports": {inside: binding}},
                "State": {"Running": True},
                "Mounts": [{"Name": cfg["project"] + "_" + suffix}],
            }
            if damage and role == "redis":
                if damage == "actual-port":
                    info["NetworkSettings"]["Ports"] = {}
                elif damage == "static-port":
                    info["HostConfig"]["PortBindings"] = {}
                elif damage == "stopped":
                    info["State"]["Running"] = False
                elif damage == "mount":
                    info["Mounts"] = [{"Name": "unrelated_user_volume"}]
            return json.dumps([info]).encode()
        if args[:4] == ["docker", "volume", "ls", "-q"]:
            # A manually-created exact-name volume has no compose-project label,
            # so a label-filtered volume listing cannot discover this collision.
            return b""
        if args[:4] == ["docker", "volume", "ls", "--format"]:
            return (cfg["project"] + "_pgdata\n").encode() if foreign_volume else b""
        if args[:3] == ["docker", "volume", "inspect"]:
            if foreign_volume and args[-1] == cfg["project"] + "_pgdata":
                return json.dumps(
                    [
                        {
                            "Name": args[-1],
                            "Labels": {"p4b.owner": "different-owner"},
                        }
                    ]
                ).encode()
            raise subprocess.CalledProcessError(1, args, stderr=b"no such volume")
        raise AssertionError(f"unexpected offline Docker query: {args[:3]}")

    def run(args, **kwargs):
        runs.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(sandbox.subprocess, "check_output", output)
    monkeypatch.setattr(sandbox.subprocess, "run", run)
    return runs


@pytest.mark.parametrize("owned_container", [False, True], ids=["new-project", "partial-project"])
def test_up_refuses_exact_name_volume_with_foreign_owner(prepared, monkeypatch, owned_container):
    path, cfg = prepared
    runs = _docker(monkeypatch, cfg, owned_container=owned_container, foreign_volume=True)
    with pytest.raises(ValueError):
        sandbox.command(path, "up")
    assert runs == []


def test_compose_process_cannot_override_validated_private_env(prepared, monkeypatch):
    path, cfg = prepared
    for key, value in {
        "PROJECT": "p4b_unrelated",
        "OWNER": "ambient_foreign_owner",
        "PG_PASSWORD": "ambient_foreign_password",
        "PG_PORT": "5432",
        "REDIS_PORT": "6379",
        "QDRANT_PORT": "6333",
    }.items():
        monkeypatch.setenv(key, value)
    runs = _docker(monkeypatch, cfg)
    sandbox.command(path, "up")
    assert len(runs) == 1
    process_env = runs[0][1].get("env")
    assert process_env is not None, "Compose must not inherit unvalidated interpolation variables"
    expected = {
        "PROJECT": cfg["project"],
        "OWNER": cfg["owner"],
        "PG_PASSWORD": cfg["password"],
        "PG_PORT": str(cfg["pg_port"]),
        "REDIS_PORT": str(cfg["redis_port"]),
        "QDRANT_PORT": str(cfg["qdrant_port"]),
    }
    # Removing keys allows --env-file to supply them; explicit correct values
    # are also valid. Inheriting ambient conflicting values is unsafe.
    assert all(process_env.get(key, value) == value for key, value in expected.items())


def test_ps_refuses_partial_project_before_direct_endpoint_access(prepared, monkeypatch):
    path, cfg = prepared
    runs = _docker(monkeypatch, cfg, owned_container=True)
    with pytest.raises(ValueError):
        sandbox.command(path, "ps")
    assert runs == []


@pytest.mark.parametrize("damage", ["actual-port", "static-port", "stopped", "mount"])
def test_ps_refuses_mismatched_or_unavailable_owned_endpoints(prepared, monkeypatch, damage):
    path, cfg = prepared
    runs = _docker(monkeypatch, cfg, complete=True, damage=damage)
    with pytest.raises(ValueError):
        sandbox.command(path, "ps")
    assert runs == []


def test_ps_accepts_complete_correctly_bound_owned_endpoints(prepared, monkeypatch):
    path, cfg = prepared
    runs = _docker(monkeypatch, cfg, complete=True)
    sandbox.command(path, "ps")
    assert len(runs) == 1
    assert runs[0][0][:3] == ["docker", "--host", "unix:///var/run/docker.sock"]


def test_roundtrip_requires_empty_database_and_validates_resume_marker(prepared):
    path, cfg = prepared
    assert migrate.roundtrip_allowed(path, cfg, []) is True
    with pytest.raises(ValueError):
        migrate.roundtrip_allowed(path, cfg, ["sessions", "orders"])
    marker = path.parent / "migration_roundtrip.json"
    marker.write_text(
        json.dumps(
            {
                "project": cfg["project"],
                "compose_sha256": cfg["compose_sha256"],
            }
        ),
        encoding="utf8",
    )
    assert migrate.roundtrip_allowed(path, cfg, ["sessions", "orders"]) is False
    marker.write_text(
        json.dumps(
            {
                "project": "p4b_foreign",
                "compose_sha256": cfg["compose_sha256"],
            }
        ),
        encoding="utf8",
    )
    with pytest.raises(ValueError):
        migrate.roundtrip_allowed(path, cfg, ["sessions", "orders"])


@pytest.mark.parametrize("tables", [[], ["sessions", "orders"]], ids=["fresh", "resumed"])
def test_migration_main_never_repeats_successful_roundtrip(prepared, monkeypatch, tables):
    path, cfg = prepared
    if tables:
        (path.parent / "migration_roundtrip.json").write_text(
            json.dumps(
                {
                    "project": cfg["project"],
                    "compose_sha256": cfg["compose_sha256"],
                }
            ),
            encoding="utf8",
        )
    monkeypatch.setattr(migrate, "live_config", lambda: (path, cfg))
    monkeypatch.setattr(migrate, "owned_command", lambda *args: None)
    monkeypatch.setattr("sys.argv", ["migrate", "--roundtrip"])

    async def table_names(url):
        return tables

    monkeypatch.setattr(migrate, "table_names", table_names)
    calls = []
    monkeypatch.setattr(
        migrate.command, "upgrade", lambda config, revision: calls.append("upgrade")
    )
    monkeypatch.setattr(
        migrate.command, "downgrade", lambda config, revision: calls.append("downgrade")
    )
    migrate.main()
    assert calls == (["upgrade", "downgrade", "upgrade"] if not tables else ["upgrade"])
