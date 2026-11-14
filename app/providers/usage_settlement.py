"""Bounded, transient response inspection; only validated scalar metadata escapes.

This parser never persists response content. Malformed, ambiguous or oversized
responses remain conservatively charged, even if the caller can consume them.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_FINISH = {"stop", "tool_calls", "function_call"}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _decode(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError()),
    )


def _counts(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, dict):
        raise ValueError()
    counts = tuple(value[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    if (
        any(type(count) is not int for count in counts)
        or counts[0] <= 0
        or counts[1] < 0
        or counts[2] != counts[0] + counts[1]
    ):
        raise ValueError()
    return counts


def _valid_function(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("name"), str)
        and bool(value["name"].strip())
        and isinstance(value.get("arguments"), str)
    )


def _valid_message(choice: dict[str, Any]) -> bool:
    message = choice.get("message")
    if (
        not isinstance(message, dict)
        or message.get("role", "assistant") != "assistant"
        or "content" not in message
        or (message["content"] is not None and not isinstance(message["content"], str))
    ):
        return False
    calls = message.get("tool_calls")
    if calls is not None and (
        not isinstance(calls, list)
        or not calls
        or any(
            not isinstance(call, dict)
            or not isinstance(call.get("id"), str)
            or not call["id"].strip()
            or call.get("type") != "function"
            or not _valid_function(call.get("function"))
            for call in calls
        )
    ):
        return False
    function = message.get("function_call")
    if function is not None and not _valid_function(function):
        return False
    reason = choice["finish_reason"]
    if reason == "tool_calls":
        return calls is not None and function is None
    if reason == "function_call":
        return function is not None and calls is None
    return isinstance(message["content"], str) and calls is None and function is None


def _valid_function_delta(value: Any) -> bool:
    # Streaming arguments and names are fragments; validate their types here,
    # without requiring a complete JSON argument string in each chunk.
    return isinstance(value, dict) and all(
        key not in value or isinstance(value[key], str) for key in ("name", "arguments")
    )


def _valid_delta(delta: Any) -> bool:
    if (
        not isinstance(delta, dict)
        or delta.get("role", "assistant") != "assistant"
        or (delta.get("content") is not None and not isinstance(delta["content"], str))
    ):
        return False
    calls = delta.get("tool_calls")
    if calls is not None and (
        not isinstance(calls, list)
        or not calls
        or any(
            not isinstance(call, dict)
            or type(call.get("index")) is not int
            or call["index"] < 0
            or ("id" in call and (not isinstance(call["id"], str) or not call["id"].strip()))
            or call.get("type", "function") != "function"
            or not _valid_function_delta(call.get("function"))
            for call in calls
        )
    ):
        return False
    function = delta.get("function_call")
    return function is None or (calls is None and _valid_function_delta(function))


class UsageEvidence:
    """Inspect JSON <=1MiB, or incremental SSE events <=64KiB each."""

    def __init__(self, *, model: str, status: int, content_type: str) -> None:
        self.model = model
        self.source = (
            "sse"
            if content_type.split(";", 1)[0].strip().lower() == "text/event-stream"
            else "json"
        )
        self.valid = 200 <= status < 300
        self.digest = hashlib.sha256()
        self.buffer = bytearray()
        self.finished = False
        self.done = False
        self.counts: tuple[int, int, int] | None = None

    def feed(self, chunk: bytes) -> None:
        self.digest.update(chunk)
        if not self.valid:
            return
        bound = 65536 if self.source == "sse" else 1048576
        # Process chunk slices so a large transport chunk cannot bypass bounds.
        for start in range(0, len(chunk), 16384):
            self.buffer.extend(chunk[start : start + 16384])
            try:
                if self.source == "sse":
                    # SSE supports LF and CRLF. Event boundaries must be complete.
                    self.buffer[:] = self.buffer.replace(b"\r\n", b"\n")
                    while b"\n\n" in self.buffer:
                        event, _, rest = self.buffer.partition(b"\n\n")
                        self.buffer[:] = rest
                        if len(event) > bound:
                            raise ValueError()
                        self._event(bytes(event))
                if len(self.buffer) > bound:
                    raise ValueError()
            except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
                self.valid = False
                self.buffer.clear()
                return

    def _event(self, event: bytes) -> None:
        lines = event.split(b"\n")
        data = []
        for line in lines:
            if line.startswith(b":") or not line:
                continue
            field, _, value = line.partition(b":")
            if field != b"data":
                raise ValueError()
            data.append(value.removeprefix(b" "))
        if not data:
            return
        if self.done:
            raise ValueError()
        raw = b"\n".join(data)
        if raw == b"[DONE]":
            if not self.finished or self.counts is None:
                raise ValueError()
            self.done = True
            return
        body = _decode(raw)
        if not isinstance(body, dict) or "error" in body or body.get("model") != self.model:
            raise ValueError()
        choices = body.get("choices")
        if not isinstance(choices, list):
            raise ValueError()
        if not choices:
            # Accept older OpenAI-compatible usage-only events after a finish.
            if body.get("usage") is None or not self.finished or self.counts is not None:
                raise ValueError()
            self.counts = _counts(body["usage"])
            return
        if self.finished or self.counts is not None or len(choices) != 1:
            raise ValueError()
        choice = choices[0]
        if (
            not isinstance(choice, dict)
            or type(choice.get("index", 0)) is not int
            or choice.get("index", 0) != 0
            or not _valid_delta(choice.get("delta"))
        ):
            raise ValueError()
        reason = choice.get("finish_reason")
        if reason is not None:
            if reason not in _FINISH:
                raise ValueError()
            self.finished = True
        if body.get("usage") is not None:
            # DeepSeek's documented final chunk carries finish and usage on the
            # same choice, with no new content. Usage before finish is invalid.
            delta = choice["delta"]
            if (
                not self.finished
                or delta.get("content") not in (None, "")
                or delta.get("tool_calls") is not None
                or delta.get("function_call") is not None
            ):
                raise ValueError()
            self.counts = _counts(body["usage"])

    def settlement(self) -> dict[str, Any] | None:
        if not self.valid:
            return None
        try:
            if self.source == "json":
                body = _decode(bytes(self.buffer))
                if not isinstance(body, dict) or "error" in body or body.get("model") != self.model:
                    return None
                choices = body.get("choices")
                if (
                    not isinstance(choices, list)
                    or len(choices) != 1
                    or not isinstance(choices[0], dict)
                    or type(choices[0].get("index", 0)) is not int
                    or choices[0].get("index", 0) != 0
                    or choices[0].get("finish_reason") not in _FINISH
                    or not _valid_message(choices[0])
                ):
                    return None
                counts = _counts(body["usage"])
            else:
                if not self.done or self.buffer.strip() or self.counts is None:
                    return None
                counts = self.counts
            return dict(
                zip(("prompt_tokens", "completion_tokens", "total_tokens"), counts, strict=True),
                response_sha256=self.digest.hexdigest(),
                source=self.source,
            )
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return None
        finally:
            self.buffer.clear()
