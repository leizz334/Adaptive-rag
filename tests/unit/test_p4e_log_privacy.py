"""Actual configured JSON handler must redact formatted args, extras and exceptions."""

import io
import logging

import pytest

from app.config.settings import Settings
from app.observability.logging import configure_logging


@pytest.mark.parametrize("kind", ["formatted_bearer", "nested_extra", "exception_dsn"])
def test_configured_json_logging_redacts_credentials(kind):
    secret = "p4e_synthetic_secret_9A7z"
    root = logging.getLogger()
    old_handlers, old_level = root.handlers[:], root.level
    stream = io.StringIO()
    try:
        configure_logging(Settings(_env_file=None, app_env="testing"))
        root.handlers[0].setStream(stream)
        logger = logging.getLogger("p4e.privacy")
        if kind == "formatted_bearer":
            logger.warning("upstream Authorization: Bearer %s", secret)
        elif kind == "nested_extra":
            logger.warning("failed", extra={"payload": {"items": [{"api_key": secret}]}})
        else:
            try:
                raise ValueError(f"postgresql+asyncpg://synthetic:{secret}@localhost/test")
            except ValueError:
                logger.exception("database failure")
        output = stream.getvalue()
        assert output and secret not in output
        assert "p4e.privacy" in output
    finally:
        root.handlers[:] = old_handlers
        root.setLevel(old_level)
