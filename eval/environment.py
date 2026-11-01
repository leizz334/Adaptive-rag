"""Resettable synthetic business environment. No DSN or production settings input."""

from pathlib import Path

from sqlalchemy import select

from app.config.settings import Settings
from app.repositories.models import (
    AuditLogRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    RefundRow,
    ReturnRow,
)
from app.services.chat_service import ChatService
from app.services.container import build_container


class BusinessEnvironment:
    def __init__(self, *, llm=None, tracer=None):
        self.llm = llm
        self.tracer = tracer
        self.container = None

    async def __aenter__(self):
        settings = Settings(
            _env_file=None,
            app_env="testing",
            database_url="sqlite+aiosqlite:///:memory:",
            deepseek_api_key="",
            embedding_api_key="",
            embedding_base_url="",
            redis_url="",
            qdrant_url="",
            local_embedding_enabled=False,
            local_embedding_force=False,
            cross_encoder_enabled=False,
            cross_encoder_force=False,
            unstructured_enabled=False,
            unstructured_force=False,
            mcp_enabled=False,
            agent_tracing_enabled=False,
            rate_limit_per_minute=10000,
            knowledge_dir=str(Path(__file__).resolve().parents[1] / "knowledge"),
        )
        self.container = await build_container(settings, seed=True)
        old = self.container.chat_service
        if self.llm is not None:
            self.container.llm = self.llm
            self.container.chat_service = ChatService(
                settings=settings,
                llm=self.llm,
                retriever=self.container.retriever,
                reranker=old._reranker,
                session_factory=self.container.session_factory,
                rate_limiter=old._rate_limiter,
                registry=old.registry,
                tracer=self.tracer,
            )
        elif self.tracer is not None:
            old._tracer = self.tracer
        self.service = self.container.chat_service
        return self

    async def __aexit__(self, *args):
        await self.container.aclose()

    async def snapshot(self):
        async with self.container.session_factory() as db:
            result = {}
            for key, model in [
                ("orders", OrderRow),
                ("items", OrderItemRow),
                ("products", ProductRow),
                ("refunds", RefundRow),
                ("returns", ReturnRow),
                ("audit", AuditLogRow),
            ]:
                rows = (
                    (await db.execute(select(model).order_by(*model.__table__.primary_key.columns)))
                    .scalars()
                    .all()
                )
                values = [
                    {
                        column.name: _scalar(getattr(row, column.name))
                        for column in model.__table__.columns
                    }
                    for row in rows
                ]
                result[key] = {v["order_id"]: v for v in values} if key == "orders" else values
            return result


def _scalar(value):
    return value.isoformat() if hasattr(value, "isoformat") else value
