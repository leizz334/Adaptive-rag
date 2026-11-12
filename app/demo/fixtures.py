"""Shared synthetic showcase records, never resetting existing business state."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.repositories.models import OrderItemRow, OrderRow


async def seed_session(db):
    for number in [95101, 95102, 95103, 95104, 95105, 95106, 95107, 95201]:
        order_id = f"ORD{number}"
        subject = "web_demo_b" if number == 95201 else "web_demo_a"
        existing = await db.get(OrderRow, order_id)
        if existing is not None:
            items = (
                await db.scalars(select(OrderItemRow).where(OrderItemRow.order_id == order_id))
            ).all()
            if (
                existing.user_id != subject
                or existing.total_cents != 6800
                or len(items) != 1
                or any(
                    (item.sku, item.name, item.quantity, item.unit_price_cents, item.customized)
                    != ("SKU-WEB-BAG", "演示帆布包", 2, 3400, False)
                    for item in items
                )
            ):
                raise ValueError("synthetic seed collision; preserve and inspect")
            continue
        db.add(
            OrderRow(
                order_id=order_id,
                user_id=subject,
                status="paid",
                total_cents=6800,
                created_at=datetime(2026, 11, 10, tzinfo=UTC),
                paid_at=datetime(2026, 11, 10, tzinfo=UTC),
            )
        )
        await db.flush()
        db.add(
            OrderItemRow(
                order_id=order_id,
                sku="SKU-WEB-BAG",
                name="演示帆布包",
                quantity=2,
                unit_price_cents=3400,
                customized=False,
            )
        )
    await db.flush()


async def seed(cfg):
    engine = create_async_engine(cfg["database_url"])
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            async with db.begin():
                await seed_session(db)
    finally:
        await engine.dispose()
