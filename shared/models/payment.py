
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base
from shared.enums import PaymentStatus, PaymentType
from shared.sa_enum import str_enum


class PaymentOrm(Base):
    """Единая таблица платежей Т-Банка.

    Идемпотентность: order_id — уникальный ключ.
    Повторные webhook не выдают товар дважды.
    """

    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int]  # в копейках
    payment_type: Mapped[PaymentType] = mapped_column(str_enum(PaymentType), index=True)
    status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus), default=PaymentStatus.NEW)
    # Доп. метаданные (tier подписки, donate-сумма, campaign_id и т.д.)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Флаг: товар уже выдан (защита от дублей webhook)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    @staticmethod
    async def create(order_id: str, user_id: int, amount: int, payment_type: PaymentType, meta: dict | None = None) -> "PaymentOrm":
        async with _session() as session:
            payment = PaymentOrm(
                order_id=order_id,
                user_id=user_id,
                amount=amount,
                payment_type=payment_type,
                meta=meta,
            )
            session.add(payment)
            await session.flush()
            await session.commit()
            return payment

    @staticmethod
    async def get_by_order_id(order_id: str) -> "PaymentOrm | None":
        async with _session() as session:
            result = await session.execute(
                select(PaymentOrm).filter(PaymentOrm.order_id == order_id)
            )
            return result.scalars().first()

    @staticmethod
    async def update_status(order_id: str, status: PaymentStatus, payment_id: str | None = None) -> "PaymentOrm | None":
        async with _session() as session:
            result = await session.execute(
                select(PaymentOrm).filter(PaymentOrm.order_id == order_id)
            )
            payment = result.scalars().first()
            if payment is None:
                return None
            payment.status = status
            if payment_id is not None and str(payment_id) != "":
                payment.payment_id = str(payment_id)
            await session.flush()
            await session.commit()
            return payment

    @staticmethod
    async def mark_fulfilled(order_id: str) -> bool:
        """Возвращает True если ТОЛЬКО ЧТО пометили выданным (защита от дублей)."""
        async with _session() as session:
            result = await session.execute(
                select(PaymentOrm).filter(PaymentOrm.order_id == order_id)
            )
            payment = result.scalars().first()
            if payment is None:
                return False
            if payment.fulfilled:
                return False
            payment.fulfilled = True
            await session.flush()
            await session.commit()
            return True


# отложенный импорт сессии
from shared.database import async_session_factory as _session  # noqa: E402
from sqlalchemy import select  # noqa: E402
