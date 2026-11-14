"""Durable, conservative admission for explicitly enabled paid HTTP attempts.

Original reservations are immutable. Only complete, validated usage may reduce
net occupancy; interrupted attempts keep their reservation and block admission.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import stat
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from decimal import Decimal, DecimalException, localcontext
from pathlib import Path
from typing import Any

import httpx

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.providers.usage_settlement import UsageEvidence


class BudgetBlocked(AppError):
    """Admission/uncertainty failures must bypass provider retries and fallback."""

    def __init__(self) -> None:
        super().__init__(
            "paid provider budget admission blocked",
            error_code=ErrorCode.LLM_PROVIDER_UNAVAILABLE,
            http_status=503,
            retryable=False,
        )


@dataclass(frozen=True)
class BudgetLimits:
    max_requests: int
    max_tokens: int
    max_usd: Decimal
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    model: str

    def __post_init__(self) -> None:
        for value in (self.max_requests, self.max_tokens):
            if type(value) is not int or value <= 0:
                raise ValueError("budget integer limits must be positive")
        for price in (self.max_usd, self.input_usd_per_million, self.output_usd_per_million):
            if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
                raise ValueError("budget decimal limits and prices must be positive and finite")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("budget model must be explicit")


_SCHEMA = (
    "CREATE TABLE metadata (fingerprint TEXT NOT NULL)",
    "CREATE TABLE attempts (id INTEGER PRIMARY KEY, tokens INTEGER NOT NULL, usd TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('pending','completed','uncertain')))",
)
_ADDITIVE_SCHEMA = (
    "CREATE TABLE reservation_evidence (attempt_id INTEGER PRIMARY KEY REFERENCES attempts(id), input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL)",
    "CREATE TABLE settlements (attempt_id INTEGER PRIMARY KEY REFERENCES attempts(id), prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL, total_tokens INTEGER NOT NULL, usd TEXT NOT NULL, response_sha256 TEXT NOT NULL, source TEXT NOT NULL)",
)


def _request_reservation(payload: bytes, limits: BudgetLimits) -> tuple[int, Decimal]:
    try:
        body = json.loads(payload.decode("utf-8"))
        output = body["max_tokens"]
        messages = body["messages"]
        if (
            body["model"] != limits.model
            or type(output) is not int
            or output <= 0
            or not isinstance(messages, list)
            or not messages
            or any(not isinstance(message, dict) for message in messages)
        ):
            raise BudgetBlocked()
        # UTF-8 bytes conservatively bound byte-BPE text tokens. Reserve the
        # entire serialized body plus explicit chat framing and maximum output.
        incoming = len(payload) + 1024 + 16 * len(messages)
        with localcontext() as context:
            context.prec = (
                sum(
                    len(value.as_tuple().digits) + abs(int(value.as_tuple().exponent))
                    for value in (limits.input_usd_per_million, limits.output_usd_per_million)
                )
                + len(str(incoming))
                + len(str(output))
                + 20
            )
            cost = (
                incoming * limits.input_usd_per_million + output * limits.output_usd_per_million
            ) / Decimal(1_000_000)
        return incoming + output, cost
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
        raise BudgetBlocked() from None


class AttemptLedger:
    """Metadata-only SQLite ledger; each reservation is an immediate transaction.

    Use a dedicated private directory on a Linux filesystem. Native Windows
    permission semantics are intentionally unsupported by this runtime helper.
    """

    def __init__(self, path: Path, limits: BudgetLimits) -> None:
        self.path = Path(os.path.abspath(path))
        self._limits = limits
        self._fingerprint = hashlib.sha256(
            json.dumps(asdict(limits), sort_keys=True, default=str).encode()
        ).hexdigest()
        try:
            if os.name == "nt":
                raise BudgetBlocked()
            self._check_path()
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.parent.stat().st_mode & 0o077:
                raise BudgetBlocked()
            created = False
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                created = True
            except FileExistsError:
                pass
            self._check_path()
            with self._transaction(validate=not created) as connection:
                if created:
                    for statement in _SCHEMA:
                        connection.execute(statement)
                    connection.execute("INSERT INTO metadata VALUES (?)", (self._fingerprint,))
                    for statement in _ADDITIVE_SCHEMA:
                        connection.execute(statement)
                else:
                    # Exact v1 schema was validated before this additive migration.
                    for statement in _ADDITIVE_SCHEMA:
                        if not connection.execute(
                            "SELECT 1 FROM sqlite_master WHERE name=?", (statement.split()[2],)
                        ).fetchone():
                            connection.execute(statement)
                self._snapshot(connection)
        except (OSError, sqlite3.Error, ValueError, DecimalException):
            raise BudgetBlocked() from None

    @property
    def limits(self) -> BudgetLimits:
        return self._limits

    def _check_path(self) -> None:
        for component in (self.path, *self.path.parents):
            if component.is_symlink():
                raise BudgetBlocked()
        if self.path.exists():
            metadata = self.path.stat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_mode & 0o077
            ):
                raise BudgetBlocked()
        for suffix in ("-journal", "-wal", "-shm"):
            if Path(str(self.path) + suffix).is_symlink():
                raise BudgetBlocked()

    @contextmanager
    def _transaction(self, *, validate: bool = True) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            self._check_path()
            if not self.path.is_file():
                raise BudgetBlocked()
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            if validate:
                schema = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
                legacy = [(_SCHEMA[1],), (_SCHEMA[0],)]
                current = [
                    (statement,) for statement in (_SCHEMA[1], _SCHEMA[0], *_ADDITIVE_SCHEMA)
                ]
                if schema not in (legacy, current):
                    raise BudgetBlocked()
                if connection.execute("SELECT fingerprint FROM metadata").fetchall() != [
                    (self._fingerprint,)
                ]:
                    raise BudgetBlocked()
                if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise BudgetBlocked()
            yield connection
            connection.commit()
        except (OSError, sqlite3.Error, ValueError, TypeError, DecimalException):
            raise BudgetBlocked() from None
        finally:
            if connection is not None:
                connection.close()

    def _snapshot(self, connection: sqlite3.Connection) -> dict[str, Any]:
        rows = connection.execute("SELECT id, tokens, usd, state FROM attempts").fetchall()
        evidence = {
            row[0]: row[1:] for row in connection.execute("SELECT * FROM reservation_evidence")
        }
        settlements = {row[0]: row[1:] for row in connection.execute("SELECT * FROM settlements")}
        ids = {row[0] for row in rows}
        if evidence.keys() - ids or settlements.keys() - ids:
            raise BudgetBlocked()
        total = Decimal(0)
        tokens = 0
        reserved_total = Decimal(0)
        reserved_tokens = 0
        states = {"pending": 0, "uncertain": 0, "completed": 0}
        for attempt, count, raw_cost, state in rows:
            cost = Decimal(raw_cost)
            if (
                type(count) is not int
                or count <= 0
                or not cost.is_finite()
                or cost <= 0
                or state not in states
            ):
                raise BudgetBlocked()
            reserved_count, reserved_cost = count, cost
            if attempt in evidence:
                incoming, output = evidence[attempt]
                if (
                    type(incoming) is not int
                    or incoming <= 0
                    or type(output) is not int
                    or output <= 0
                    or incoming + output != count
                    or self._cost(incoming, output) != cost
                ):
                    raise BudgetBlocked()
            if attempt in settlements:
                if state != "completed" or attempt not in evidence:
                    raise BudgetBlocked()
                prompt, completion, count, raw_net, digest, source = settlements[attempt]
                cost = self._validated_settlement(
                    prompt, completion, count, digest, source, evidence[attempt], reserved_cost
                )
                if str(cost) != raw_net:
                    raise BudgetBlocked()
            with localcontext() as context:
                context.prec = (
                    len(str(total)) + len(raw_cost) + abs(int(cost.as_tuple().exponent)) + 20
                )
                total += cost
                reserved_total += reserved_cost
            tokens += count
            reserved_tokens += reserved_count
            states[state] += 1
        return {
            "requests": len(rows),
            "tokens": tokens,
            "usd": str(total),
            "reserved_tokens": reserved_tokens,
            "reserved_usd": str(reserved_total),
            "settled": len(settlements),
            **states,
        }

    def _cost(self, incoming: int, output: int) -> Decimal:
        with localcontext() as context:
            context.prec = (
                sum(
                    len(value.as_tuple().digits) + abs(int(value.as_tuple().exponent))
                    for value in (
                        self.limits.input_usd_per_million,
                        self.limits.output_usd_per_million,
                    )
                )
                + len(str(incoming))
                + len(str(output))
                + 20
            )
            return (
                incoming * self.limits.input_usd_per_million
                + output * self.limits.output_usd_per_million
            ) / Decimal(1_000_000)

    def _validated_settlement(
        self,
        prompt: int,
        completion: int,
        total: int,
        digest: str,
        source: str,
        evidence: tuple,
        reserved_cost: Decimal,
    ) -> Decimal:
        if (
            any(type(value) is not int for value in (prompt, completion, total))
            or prompt <= 0
            or completion < 0
            or total != prompt + completion
            or prompt > evidence[0]
            or completion > evidence[1]
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or source not in ("json", "sse")
        ):
            raise BudgetBlocked()
        cost = self._cost(prompt, completion)
        if cost > reserved_cost:
            raise BudgetBlocked()
        return cost

    def settle(
        self,
        attempt: int,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        response_sha256: str,
        source: str,
    ) -> None:
        """Atomically append trusted usage and complete a pending attempt.

        Callers must have consumed and closed a successful provider response.
        Exact replay is idempotent; conflicting evidence is always rejected.
        Historical attempts without reservation evidence cannot be settled.
        """
        if type(attempt) is not int:
            raise BudgetBlocked()
        with self._transaction() as connection:
            self._snapshot(connection)
            row = connection.execute(
                "SELECT a.usd,a.state,e.input_tokens,e.output_tokens FROM attempts a "
                "JOIN reservation_evidence e ON a.id=e.attempt_id WHERE a.id=?",
                (attempt,),
            ).fetchone()
            if row is None:
                raise BudgetBlocked()
            cost = self._validated_settlement(
                prompt_tokens,
                completion_tokens,
                total_tokens,
                response_sha256,
                source,
                row[2:],
                Decimal(row[0]),
            )
            record = (
                attempt,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                str(cost),
                response_sha256,
                source,
            )
            previous = connection.execute(
                "SELECT * FROM settlements WHERE attempt_id=?", (attempt,)
            ).fetchone()
            if previous is not None:
                if previous != record:
                    raise BudgetBlocked()
                return
            if row[1] != "pending":
                raise BudgetBlocked()
            connection.execute("INSERT INTO settlements VALUES (?,?,?,?,?,?,?)", record)
            connection.execute("UPDATE attempts SET state='completed' WHERE id=?", (attempt,))

    def snapshot(self) -> dict[str, Any]:
        with self._transaction() as connection:
            return self._snapshot(connection)

    def ensure_ready(self) -> None:
        snapshot = self.snapshot()
        if snapshot["pending"] or snapshot["uncertain"]:
            raise BudgetBlocked()

    def reserve(self, payload: bytes) -> int:
        tokens, cost = _request_reservation(payload, self.limits)
        with self._transaction() as connection:
            snapshot = self._snapshot(connection)
            with localcontext() as context:
                context.prec = (
                    len(snapshot["usd"]) + len(str(cost)) + abs(int(cost.as_tuple().exponent)) + 20
                )
                total = Decimal(snapshot["usd"]) + cost
            if (
                snapshot["pending"]
                or snapshot["uncertain"]
                or snapshot["requests"] + 1 > self.limits.max_requests
                or snapshot["tokens"] + tokens > self.limits.max_tokens
                or total > self.limits.max_usd
                or tokens > 2**63 - 1
            ):
                raise BudgetBlocked()
            cursor = connection.execute(
                "INSERT INTO attempts(tokens, usd, state) VALUES (?, ?, 'pending')",
                (tokens, str(cost)),
            )
            assert cursor.lastrowid is not None
            output = json.loads(payload)["max_tokens"]
            connection.execute(
                "INSERT INTO reservation_evidence VALUES (?,?,?)",
                (cursor.lastrowid, tokens - output, output),
            )
            return cursor.lastrowid

    def _transition(self, attempt: int, state: str) -> None:
        with self._transaction() as connection:
            cursor = connection.execute(
                "UPDATE attempts SET state=? WHERE id=? AND state='pending'", (state, attempt)
            )
            if cursor.rowcount != 1:
                raise BudgetBlocked()

    def complete(self, attempt: int) -> None:
        self._transition(attempt, "completed")

    def uncertain(self, attempt: int) -> None:
        self._transition(attempt, "uncertain")


class _BudgetStream(httpx.AsyncByteStream):
    def __init__(
        self,
        ledger: AttemptLedger,
        attempt: int,
        inner: httpx.AsyncByteStream,
        evidence: UsageEvidence,
    ) -> None:
        self._ledger = ledger
        self._attempt = attempt
        self._inner = inner
        self._finished = False
        self._uncertain = False
        self._cancelled = False
        self._exhausted = False
        self._evidence = evidence
        self._close_lock = asyncio.Lock()

    def _mark_uncertain(self) -> None:
        if not self._finished and not self._uncertain:
            self._uncertain = True
            self._ledger.uncertain(self._attempt)

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._inner:
                self._evidence.feed(chunk)
                yield chunk
            self._exhausted = True
        except asyncio.CancelledError:
            self._cancelled = True
            with suppress(BudgetBlocked):
                self._mark_uncertain()
            raise
        except GeneratorExit:
            self._mark_uncertain()
            raise
        except Exception:
            self._mark_uncertain()
            raise BudgetBlocked() from None

    async def aclose(self) -> None:
        async with self._close_lock:
            await self._close()

    async def _close(self) -> None:
        if self._finished:
            return
        try:
            await self._inner.aclose()
        except asyncio.CancelledError:
            self._cancelled = True
            with suppress(BudgetBlocked):
                self._mark_uncertain()
            raise
        except Exception:
            self._mark_uncertain()
            raise BudgetBlocked() from None
        if self._uncertain or self._cancelled:
            return
        if not self._exhausted:
            self._mark_uncertain()
            raise BudgetBlocked()
        settlement = self._evidence.settlement()
        try:
            if settlement is None:
                self._ledger.complete(self._attempt)
            else:
                try:
                    self._ledger.settle(self._attempt, **settlement)
                except BudgetBlocked:
                    # Invalid supplier counts (e.g. above reservation) cannot
                    # refund capacity. A corrupt ledger still fails completion.
                    self._ledger.complete(self._attempt)
            self._finished = True
        except BudgetBlocked:
            with suppress(BudgetBlocked):
                self._mark_uncertain()
            raise


class BudgetedTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        ledger: AttemptLedger,
        inner: httpx.AsyncBaseTransport | None = None,
        *,
        allowed_base_url: str = "https://api.deepseek.com",
        dispatch_enabled: bool = True,
    ) -> None:
        self._ledger = ledger
        self._dispatch_enabled = dispatch_enabled is True
        self._base = httpx.URL(allowed_base_url)
        if (
            self._base.scheme != "https"
            or not self._base.host
            or self._base.username
            or self._base.password
            or self._base.query
            or self._base.fragment
            or self._base.path.rstrip("/") not in ("", "/v1")
        ):
            raise BudgetBlocked()
        self._inner = inner if inner is not None else httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if (
            not self._dispatch_enabled
            or request.method != "POST"
            or (url.scheme, url.host, url.port)
            != (self._base.scheme, self._base.host, self._base.port)
            or url.path != self._base.path.rstrip("/") + "/chat/completions"
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            raise BudgetBlocked()
        attempt = self._ledger.reserve(await request.aread())
        try:
            response = await self._inner.handle_async_request(request)
            if not isinstance(response.stream, httpx.AsyncByteStream):
                raise BudgetBlocked()
        except asyncio.CancelledError:
            with suppress(BudgetBlocked):
                self._ledger.uncertain(attempt)
            raise
        except Exception:
            self._ledger.uncertain(attempt)
            raise BudgetBlocked() from None
        # Some injected transports return already-buffered responses. Build a
        # fresh response so HTTPX still consumes the accounting stream once.
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=_BudgetStream(
                self._ledger,
                attempt,
                response.stream,
                UsageEvidence(
                    model=self._ledger.limits.model,
                    status=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                ),
            ),
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self._inner.aclose()
