"""Structured JSON logging setup."""

from __future__ import annotations

import logging
from contextvars import ContextVar

try:
    from pythonjsonlogger.jsonlogger import JsonFormatter
except ImportError:  # python-json-logger >= 3
    from pythonjsonlogger.json import JsonFormatter

from app.config.settings import Settings
from app.core.security import redact_log_text, redact_mapping

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.request_id = request_id_var.get()
        if isinstance(record.msg, dict):
            record.msg = redact_mapping(record.msg)
        record.msg = redact_log_text(record.getMessage())
        record.args = ()
        return True


class RedactingJsonFormatter(JsonFormatter):
    def add_fields(self, log_data, record, message_dict):
        super().add_fields(log_data, record, message_dict)
        log_data.update(redact_mapping(log_data))

    def format(self, record: logging.LogRecord) -> str:
        # Exception formatting happens after filters; redact the final output too.
        return redact_log_text(super().format(record))


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    formatter = RedactingJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(request_id)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
