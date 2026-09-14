
from datetime import datetime

from sqlalchemy import BigInteger, String, Integer, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory


class DonationOrm(Base):
    """Донаты пользователей."""

    __tablename__ = "donation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int]  # копейки
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    public: Mapped[bool] = mapped_column(default=False)  # публичная благодарность
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @staticmethod
    async def create(user_id: int, amount: int, order_id: str, message: str | None = None, public: bool = False) -> "DonationOrm":
        async with async_session_factory() as session:
            d = DonationOrm(
                user_id=user_id,
                amount=amount,
                order_id=order_id,
                message=message,
                public=public,
            )
            session.add(d)
            await session.commit()
            return d

    @staticmethod
    async def get_total() -> int:
        async with async_session_factory() as session:
            result = await session.execute(select(DonationOrm))
            return sum(d.amount for d in result.scalars().all())
