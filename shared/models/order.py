
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory


class OrderOrm(Base):
    """Разовые покупки (цифровые товары, разблокировка на 24ч, расшифровка голосовых)."""

    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int]  # копейки
    product: Mapped[str] = mapped_column(String(64), index=True)  # 'status_unique', 'ai_batch', 'voice_long', 'unlock_24h'
    fulfilled: Mapped[bool] = mapped_column(default=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @staticmethod
    async def create(order_id: str, user_id: int, amount: int, product: str, meta: dict | None = None) -> "OrderOrm":
        async with async_session_factory() as session:
            o = OrderOrm(
                order_id=order_id,
                user_id=user_id,
                amount=amount,
                product=product,
                meta=meta,
            )
            session.add(o)
            await session.commit()
            return o

    @staticmethod
    async def get_by_order_id(order_id: str) -> "OrderOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(select(OrderOrm).filter(OrderOrm.order_id == order_id))
            return result.scalars().first()
