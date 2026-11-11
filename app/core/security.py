"""Log redaction and PII masking. Never log secrets or raw identifiers."""

from __future__ import annotations

import re

from app.core.constants import PII_MASK

_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "cookie",
        "secret",
    }
)

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_ID_CARD = re.compile(r"\b(\d{6})\d{8,10}(\d{2}[\dXx])\b")
_BANK_CARD = re.compile(r"\b(\d{4})\d{8,11}(\d{4})\b")
_ORDER_ID = re.compile(r"\b(ORD)[-_]?(\d{4})\d+(\d{2})\b", re.IGNORECASE)


# Apply at the logging boundary, separately from corpus PII cleaning.
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s\"'<>\\]+")
_DSN_PASSWORD = re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^\s/:@]+:)[^\s@]+(@)")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api_key|apikey|access_token|refresh_token|password|secret)[\"']?\s*[=:]\s*)"
    r"(?:([\"'])(.*?)\2|([^\s,;\"'<>\\]+))"
)


def redact_log_text(text: str) -> str:
    text = _BEARER.sub("Bearer " + PII_MASK, text)
    text = _DSN_PASSWORD.sub(lambda m: m[1] + PII_MASK + m[2], text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: m[1] + (m[2] or "") + PII_MASK + (m[2] or ""), text)
    return mask_pii(text)


def _redact_log_value(value: object) -> object:
    if isinstance(value, str):
        return redact_log_text(value)
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list | tuple):
        return [_redact_log_value(item) for item in value]
    return value


def redact_mapping(payload: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if key.lower() in _SECRET_KEYS:
            redacted[key] = PII_MASK
        else:
            redacted[key] = _redact_log_value(value)
    return redacted


def mask_pii(text: str) -> str:
    text = _PHONE.sub(rf"\1{PII_MASK}\2", text)
    text = _ID_CARD.sub(rf"\1{PII_MASK}\2", text)
    text = _BANK_CARD.sub(rf"\1{PII_MASK}\2", text)
    text = _ORDER_ID.sub(rf"\1{PII_MASK}\3", text)
    return text
