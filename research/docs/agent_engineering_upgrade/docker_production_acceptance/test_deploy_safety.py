"""Fault injection tests never invoke Docker or touch a production path."""

import json
from unittest.mock import Mock

import pytest

from research.docs.agent_engineering_upgrade.docker_production_acceptance import deploy


@pytest.fixture
def context(tmp_path, monkeypatch):
    private = tmp_path / "private"
    evidence = tmp_path / "evidence"
    private.mkdir()
    evidence.mkdir()
    (evidence / "before-data.json").write_text("{}")
    (evidence / "rollback.json").write_text(json.dumps({"old_image_id": "old-image"}))
    monkeypatch.setattr(deploy, "PRIVATE", private)
    monkeypatch.setattr(deploy, "EVIDENCE", evidence)
    monkeypatch.setattr(deploy.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(deploy, "fingerprint", Mock(return_value={}))
    compose = Mock(return_value="")
    monkeypatch.setattr(deploy, "compose", compose)
    monkeypatch.setattr(
        deploy, "status", Mock(return_value=[{"image": "old-image", "health": "healthy"}])
    )
    return compose


@pytest.mark.parametrize("failure", ["compose", "status", "fingerprint"])
def test_failure_after_mutation_attempt_rolls_back_and_checks_health(context, monkeypatch, failure):
    if failure == "compose":
        context.side_effect = [RuntimeError("simulated replacement failure"), ""]
    elif failure == "status":
        monkeypatch.setattr(
            deploy,
            "status",
            Mock(
                side_effect=[
                    RuntimeError("inspection failed"),
                    [{"image": "old-image", "health": "healthy"}],
                ]
            ),
        )
    else:
        monkeypatch.setattr(
            deploy, "fingerprint", Mock(side_effect=[{}, RuntimeError("read failed")])
        )
    with pytest.raises(RuntimeError):
        deploy.upgrade_api()
    assert (
        context.call_count == 2
    ), "Every failure after a replacement attempt must attempt API-only rollback"
    assert context.call_args.args[0] == deploy.PRIVATE / "rollback.json"
    assert context.call_args.args[1:] == ("up", "-d", "--no-deps", "--no-build", "api")
    assert deploy.status.called, "Restoration must be inspected before reporting recovery"


def test_rollback_unhealthy_never_reports_restored(context, monkeypatch):
    context.side_effect = [RuntimeError("replacement failed"), ""]
    monkeypatch.setattr(
        deploy, "status", Mock(return_value=[{"image": "old-image", "health": "unhealthy"}])
    )
    with pytest.raises(RuntimeError, match="rollback not verified"):
        deploy.upgrade_api()


def test_preflight_failure_never_replaces_api(context, monkeypatch):
    monkeypatch.setattr(deploy, "fingerprint", Mock(return_value={"changed": True}))
    with pytest.raises(AssertionError):
        deploy.upgrade_api()
    context.assert_not_called()
