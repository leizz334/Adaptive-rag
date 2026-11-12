"""Deployment contract guards, not a substitute for real container acceptance."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def compose():
    return yaml.safe_load((ROOT / "compose.showcase.yml").read_text())


def test_internal_dependencies_and_no_host_database_ports_or_fixed_resources():
    c = compose()
    assert c["networks"]["showcase"]["internal"] is True
    for name in ["postgres", "redis", "qdrant"]:
        assert not c["services"][name].get("ports")
        assert "container_name" not in c["services"][name]
    assert c["services"]["api"]["ports"] == ["127.0.0.1:${SHOWCASE_PORT:-8000}:8000"]
    assert not any(v.get("external") or v.get("name") for v in c["volumes"].values())


def test_readiness_and_secret_volume_separation():
    c = compose()
    s = c["services"]
    assert (
        s["postgres"]["environment"]["POSTGRES_PASSWORD_FILE"]
        == "/run/showcase-db/postgres_password"
    )
    assert "POSTGRES_PASSWORD" not in s["postgres"]["environment"]
    assert not any("showcase_state" in v for v in s["postgres"]["volumes"])
    assert s["api"]["depends_on"]["initialize"]["condition"] == "service_completed_successfully"
    for dep in ["postgres", "redis", "qdrant"]:
        assert s["api"]["depends_on"][dep]["condition"] == "service_healthy"
        assert s[dep]["healthcheck"]["test"]
    assert s["bootstrap"]["network_mode"] == "none"
    assert s["api"]["user"] == "1000:1000"


def test_context_excludes_nested_user_secrets_and_does_not_copy_research_results():
    ignore = (ROOT / ".dockerignore").read_text()
    assert "**/.private" in ignore and "**/.env*" in ignore and "**/node_modules" in ignore
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "AS showcase" in dockerfile and "COPY alembic " in dockerfile
    assert "COPY research " not in dockerfile and "COPY . " not in dockerfile


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker CLI absent; not runtime acceptance")
def test_host_paid_keys_are_not_interpolated_into_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-a-real-secret-must-not-inherit")
    monkeypatch.setenv("AUTH_CREDENTIALS", "do-not-inherit-registry")
    empty = tmp_path / "empty"
    empty.write_text("")
    output = subprocess.check_output(
        [
            "docker",
            "compose",
            "--env-file",
            str(empty),
            "-f",
            str(ROOT / "compose.showcase.yml"),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
    )
    c = json.loads(output)
    env = c["services"]["api"]["environment"]
    assert env["DEEPSEEK_API_KEY"] == "" and env["AUTH_CREDENTIALS"] == ""
    assert (
        b"not-a-real-secret-must-not-inherit" not in output
        and b"do-not-inherit-registry" not in output
    )


def test_only_api_bridges_private_dependencies_to_loopback_web_edge():
    c = compose()
    assert c["services"]["api"]["networks"] == ["showcase", "web"]
    assert c["networks"]["web"].get("internal", False) is False
    for service in ("postgres", "redis", "qdrant", "initialize"):
        assert c["services"][service]["networks"] == ["showcase"]
