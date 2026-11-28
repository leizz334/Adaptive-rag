"""Durable accounting at the only HTTP boundary of the paid replay."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

MODEL = "deepseek-flash"
HOST = "api.deepseek.com"
REGULAR_PATH = "/chat/completions"
BETA_PATH = "/beta/chat/completions"
RATE = {"cache_hit": 40, "cache_miss": 2_000, "completion": 8_000}  # nanoyuan per token
SCALE = 10**9
REQUEST_SCOPE: ContextVar[dict | None] = ContextVar("p35_paid_request", default=None)


class RunStopped(RuntimeError):
    """Paid work cannot safely continue with the available evidence or budget."""


def cny(nanoyuan):
    return f"{Decimal(nanoyuan) / SCALE:.9f}"


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def append_jsonl(path, value):
    with path.open("a", encoding="utf-8", newline="\n") as out:
        out.write(encode(value) + "\n")
        out.flush()
        os.fsync(out.fileno())


def reservation(body):
    output = body.get("max_tokens")
    if body.get("model") != MODEL or type(output) is not int or not 0 < output <= 4096:
        raise RunStopped("Unapproved model or completion-token limit")
    if body.get("stream") or body.get("n", 1) != 1:
        raise RunStopped("Only a single, non-streaming completion can be billed by this ledger")
    # Reuse the repository's conservative one-token-per-UTF-8-byte envelope,
    # including the entire schema and a request framing allowance.
    prompt = len(encode(body).encode("utf-8")) + 128
    return prompt, prompt * RATE["cache_miss"] + output * RATE["completion"]


def metered_usage(body):
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    fields = (
        "prompt_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
        "completion_tokens",
        "total_tokens",
    )
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in fields):
        return None
    prompt, hits, misses, completion, total = (usage[key] for key in fields)
    if prompt <= 0 or hits + misses != prompt or prompt + completion != total:
        return None
    return {key: usage[key] for key in fields}


class Ledger:
    def __init__(self, path: Path, *, cap_cny, max_requests):
        limit = Decimal(cap_cny) * SCALE
        if limit != limit.to_integral_value() or not 0 < limit <= 3500000000 or max_requests < 1:
            raise ValueError("Invalid paid-replay limits")
        self.path = path
        self.cap = int(limit)
        self.max_requests = max_requests
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS limits (id PRIMARY KEY, cap, requests, model, tariff)"
            )
            db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE,
                    admitted TEXT NOT NULL, scope TEXT NOT NULL, endpoint TEXT NOT NULL,
                    request TEXT NOT NULL, prompt_bound INTEGER NOT NULL, reserve INTEGER NOT NULL,
                    status TEXT NOT NULL, http_status INTEGER, response TEXT, usage TEXT,
                    actual INTEGER, latency_ms REAL
                )
            """)
            identity = (self.cap, self.max_requests, MODEL, encode(RATE))
            db.execute("INSERT OR IGNORE INTO limits VALUES (1, ?, ?, ?, ?)", identity)
            limits = db.execute("SELECT cap, requests, model, tariff FROM limits").fetchone()
            if tuple(limits) != identity:
                raise RunStopped("The ledger has a different frozen model, tariff, or budget")
            self._assert_settled(db)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _assert_settled(db):
        if db.execute("SELECT 1 FROM requests WHERE actual IS NULL LIMIT 1").fetchone():
            raise RunStopped("An unsettled paid attempt retains its reserved spend")
        if db.execute("SELECT 1 FROM requests WHERE status = 'bound_exceeded' LIMIT 1").fetchone():
            raise RunStopped("A prior provider usage record exceeded its conservative bound")

    def admit(self, scope, endpoint, body):
        prompt_bound, reserve = reservation(body)
        with self.transaction() as db:
            self._assert_settled(db)
            count, cost = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(actual), 0) FROM requests"
            ).fetchone()
            if count >= self.max_requests:
                raise RunStopped("Paid request count cap reached")
            if cost + reserve > self.cap:
                raise RunStopped("Paid CNY budget would be exceeded by this request")
            key = scope.get("request_key", scope["job"])
            if db.execute("SELECT 1 FROM requests WHERE key = ?", (key,)).fetchone():
                raise RunStopped(f"Request identity already exists in ledger: {key}")
            row = db.execute(
                """
                INSERT INTO requests
                    (key, admitted, scope, endpoint, request, prompt_bound, reserve, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'in_flight')
            """,
                (
                    key,
                    datetime.now(UTC).isoformat(),
                    encode(scope),
                    endpoint,
                    encode(body),
                    prompt_bound,
                    reserve,
                ),
            )
            return row.lastrowid

    def settle(self, attempt, http_status, body, latency_ms):
        usage = metered_usage(body)
        with self.transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE id = ?", (attempt,)).fetchone()
            if row is None or row["status"] != "in_flight":
                raise RunStopped("Attempt is missing or already settled")
            actual = None
            if usage is not None and 200 <= http_status < 300:
                actual = (
                    usage["prompt_cache_hit_tokens"] * RATE["cache_hit"]
                    + usage["prompt_cache_miss_tokens"] * RATE["cache_miss"]
                    + usage["completion_tokens"] * RATE["completion"]
                )
                request = json.loads(row["request"])
                within_bound = (
                    usage["prompt_tokens"] <= row["prompt_bound"]
                    and usage["completion_tokens"] <= request["max_tokens"]
                )
                status = "billed" if within_bound else "bound_exceeded"
            elif (
                row["endpoint"] == BETA_PATH
                and json.loads(row["scope"]).get("strict_probe") is True
                and http_status in {400, 404, 422}
                and isinstance(body, dict)
                and isinstance(body.get("error"), dict)
                and "usage" not in body
                and "choices" not in body
            ):
                status, actual = "beta_rejected", 0
            else:
                status = "uncertain"
            db.execute(
                """
                UPDATE requests SET status=?, http_status=?, response=?, usage=?, actual=?, latency_ms=?
                WHERE id=?
            """,
                (status, http_status, encode(body), encode(usage), actual, latency_ms, attempt),
            )
        if status == "uncertain":
            raise RunStopped("Provider response has no reconcilable usage; reserved spend retained")
        if status == "bound_exceeded":
            raise RunStopped("Provider usage exceeded the conservative request bound")

    def requests(self):
        with self.transaction() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM requests ORDER BY id")]
        for row in rows:
            for key in ("scope", "request", "response", "usage"):
                row[key] = json.loads(row[key]) if row[key] is not None else None
            row["actual_cost_cny"] = cny(row["actual"]) if row["actual"] is not None else None
            row["reserved_cny"] = cny(row["reserve"])
        return rows

    def totals(self):
        rows = self.requests()
        outstanding = sum(row["reserve"] for row in rows if row["actual"] is None)
        billed = sum(row["actual"] or 0 for row in rows)
        return {
            "model": MODEL,
            "tariff_cny_per_million_tokens": {key: value / 1000 for key, value in RATE.items()},
            "cap_cny": cny(self.cap),
            "max_requests": self.max_requests,
            "attempts": len(rows),
            "billed": sum(row["status"] in {"billed", "bound_exceeded"} for row in rows),
            "actual_cost_cny": cny(billed),
            "outstanding_reserve_cny": cny(outstanding),
            "remaining_admission_budget_cny": cny(self.cap - billed - outstanding),
        }


class MeteredTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger, upstream=None):
        self.ledger = ledger
        self.upstream = upstream or httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        if (
            request.method != "POST"
            or request.url.scheme != "https"
            or request.url.host != HOST
            or request.url.port not in {None, 443}
            or request.url.query
            or request.url.path not in {REGULAR_PATH, BETA_PATH}
        ):
            raise RunStopped(
                "The paid replay only sends to the official DeepSeek completion endpoint"
            )
        scope = REQUEST_SCOPE.get()
        if scope is None:
            raise RunStopped("A paid request lacks its predeclared case and arm")
        body = json.loads(await request.aread())
        scope["requests"] = scope.get("requests", 0) + 1
        context = {**scope, "request_key": f"{scope['job']}:{scope['requests']}"}
        attempt = self.ledger.admit(context, request.url.path, body)
        started = time.perf_counter()
        try:
            response = await self.upstream.handle_async_request(request)
            raw = await response.aread()
            await response.aclose()
        except httpx.HTTPError:
            raise RunStopped("Paid HTTP attempt was interrupted; reserved spend retained") from None
        elapsed = (time.perf_counter() - started) * 1000
        # Authorization headers are never written. Remove any credential echoed in an error body.
        credential = request.headers.get("Authorization", "").removeprefix("Bearer ").encode()
        saved = raw.replace(credential, b"[REDACTED]") if credential else raw
        try:
            saved_body = json.loads(saved)
        except (ValueError, UnicodeDecodeError):
            saved_body = {"non_json_response": saved.decode("utf-8", errors="replace")}
        self.ledger.settle(attempt, response.status_code, saved_body, elapsed)
        return response

    async def aclose(self):
        await self.upstream.aclose()
