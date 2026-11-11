"""A demo token must never be world-readable, including while being written."""

import os
import stat

from research.docs.agent_engineering_upgrade.p4_final_acceptance import deploy


def test_token_file_is_private_before_first_byte_is_written(tmp_path, monkeypatch):
    real_dump = deploy.json.dump

    def verify_at_write(value, stream):
        assert stat.S_IMODE(os.fstat(stream.fileno()).st_mode) == 0o600
        return real_dump(value, stream)

    monkeypatch.setattr(deploy.json, "dump", verify_at_write)
    old_umask = os.umask(0o022)
    try:
        value = deploy.private_api_config(tmp_path / "manifest.json")
        assert value["token"]
    finally:
        os.umask(old_umask)
