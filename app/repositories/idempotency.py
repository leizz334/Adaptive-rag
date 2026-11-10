"""Idempotency-key storage for write operations."""

import json

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.repositories.models import IdempotencyRow


class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_if_matches(self, key: str, fingerprint: str) -> dict | None:
        row = await self._session.get(IdempotencyRow, key)
        if row is None:
            return None
        if row.fingerprint != fingerprint:
            raise AppError(
                "idempotency key reused with different payload",
                error_code=ErrorCode.IDEMPOTENCY_CONFLICT,
                http_status=409,
            )
        return json.loads(row.response_json)

    async def put(self, key: str, fingerprint: str, response: dict) -> None:
        dialect = self._session.get_bind().dialect.name
        if dialect in {"postgresql", "sqlite"}:
            insert = pg_insert if dialect == "postgresql" else sqlite_insert
            statement = (
                insert(IdempotencyRow)
                .values(
                    key=key,
                    fingerprint=fingerprint,
                    response_json=json.dumps(response, ensure_ascii=False),
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
            await self._session.execute(statement)
            # A competing transaction has committed before ON CONFLICT returns.
            await self.get_if_matches(key, fingerprint)
            return
        existing = await self.get_if_matches(key, fingerprint)
        if existing is None:
            self._session.add(
                IdempotencyRow(
                    key=key,
                    fingerprint=fingerprint,
                    response_json=json.dumps(response, ensure_ascii=False),
                )
            )
