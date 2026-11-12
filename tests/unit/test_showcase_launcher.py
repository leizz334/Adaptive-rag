import importlib
import json
import os

import pytest


def launcher():
    return importlib.import_module("scripts.showcase")


@pytest.mark.parametrize("run_id", ["../else", "UPPER", "", "a/b", "a" * 25, "test;rm", "test.dot"])
def test_run_id_cannot_target_user_paths_or_other_projects(run_id):
    with pytest.raises(ValueError):
        launcher().run_paths(run_id)


def test_init_refuses_existing_run_before_any_resource_or_credential_write(tmp_path, monkeypatch):
    m = launcher()
    monkeypatch.setattr(m, "PRIVATE", tmp_path)
    directory = tmp_path / "existing"
    directory.mkdir()
    secret = directory / "demo_api.json"
    secret.write_text("keep-original")
    with pytest.raises(FileExistsError):
        m.initialize("existing")
    assert secret.read_text() == "keep-original"


def test_saved_manifest_cannot_redirect_to_another_run(tmp_path, monkeypatch):
    m = launcher()
    monkeypatch.setattr(m, "PRIVATE", tmp_path)
    directory = tmp_path / "alpha"
    directory.mkdir()
    (directory / "run.json").write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": "alpha",
                "project": "p4b_showcase_alpha",
                "manifest": "/tmp/unrelated/manifest.json",
            }
        )
    )
    with pytest.raises(ValueError, match="target"):
        m.read_run("alpha")


def test_stale_pid_or_foreign_command_never_authorizes_process_stop():
    m = launcher()
    record = {"run_id": "alpha", "start_ticks": "123"}
    facts = {
        "start_ticks": "123",
        "uid": os.getuid(),
        "cwd": str(m.ROOT),
        "cmdline": ["python", "-m", "scripts.showcase", "serve", "--run-id", "alpha"],
    }
    assert m.matching_process(record, facts)
    for changes in [
        {"start_ticks": "124"},
        {"cwd": "/other"},
        {"uid": os.getuid() + 1},
        {"cmdline": ["python", "-m", "scripts.showcase", "serve", "--run-id", "other"]},
        {"cmdline": ["python", "-m", "unrelated", "serve", "--run-id", "alpha"]},
    ]:
        assert not m.matching_process(record, facts | changes)


def test_public_info_does_not_return_plaintext_tokens_or_registry(tmp_path, monkeypatch):
    m = launcher()
    monkeypatch.setattr(m, "PRIVATE", tmp_path)
    directory = tmp_path / "alpha"
    directory.mkdir()
    api = directory / "demo_api.json"
    api.write_text(
        json.dumps(
            {"port": 12345, "tokens": {"a": "DO_NOT_EXPORT"}, "credentials": "PRIVATE_REGISTRY"}
        )
    )
    info = m.public_info("alpha")
    serialized = json.dumps(info)
    assert "DO_NOT_EXPORT" not in serialized and "PRIVATE_REGISTRY" not in serialized
    assert info["url"] == "http://127.0.0.1:12345" and info["paid_requests"] == 0


def test_loopback_showcase_ignores_ambient_external_proxies_without_touching_user_env_file(
    monkeypatch,
):
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:7890/")
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:1234")
    monkeypatch.setenv("SHOWCASE_KEEP", "untouched")
    launcher().clear_proxy_environment()
    assert not any(key.lower().endswith("_proxy") for key in os.environ)
    assert os.environ["SHOWCASE_KEEP"] == "untouched"
