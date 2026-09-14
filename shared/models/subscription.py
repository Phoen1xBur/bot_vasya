
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, String, Integer, DateTime, Boolean, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory
from shared.enums import SubscriptionTier, SubscriptionStatus

# Базовые цены подписок (копейки). Настраиваются в админке.
TIER_PRICES_KOPECKS = {
    SubscriptionTier.VIP: 19900,
    SubscriptionTier.PREMIUM: 39900,
    SubscriptionTier.ELITE: 79900,
}

# Множители лимитов и бонусы к заработку (только к работе)
TIER_LIMIT_MULTIPLIER = {
    SubscriptionTier.FREE: 1,
    SubscriptionTier.VIP: 2,
    SubscriptionTier.PREMIUM: 4,
    SubscriptionTier.ELITE: 0,  # 0 = безлимит
}

TIER_WORK_BONUS = {
    SubscriptionTier.FREE: 0.0,
    SubscriptionTier.VIP: 0.10,
    SubscriptionTier.PREMIUM: 0.25,
    SubscriptionTier.ELITE: 0.50,
}

TIER_FREE_JAIL_PER_DAY = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.VIP: 1,
    SubscriptionTier.PREMIUM: 3,
    SubscriptionTier.ELITE: 5,
}

TIER_AI_DAILY_LIMIT = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.VIP: 10,
    SubscriptionTier.PREMIUM: 50,
    SubscriptionTier.ELITE: -1,  # безлимит
}

TIER_TAG = {
    SubscriptionTier.FREE: "",
    SubscriptionTier.VIP: "VIP",
    SubscriptionTier.PREMIUM: "Premium",
    SubscriptionTier.ELITE: "Elite",
}


class SubscriptionOrm(Base):
    """Подписка пользователя (привязана к Telegram user_id, не к чату)."""

    __tablename__ = "subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tier: Mapped[SubscriptionTier] = mapped_column(default=SubscriptionTier.FREE)
    status: Mapped[SubscriptionStatus] = mapped_column(default=SubscriptionStatus.PENDING)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ключ рекуррентного списания Т-Банка (для автопродления)
    recurring_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )

    @staticmethod
    async def get_active(user_id: int) -> "SubscriptionOrm | None":
        """Активная подписка (status=ACTIVE и не истекла)."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm).filter(
                    SubscriptionOrm.user_id == user_id,
                    SubscriptionOrm.status == SubscriptionStatus.ACTIVE,
                    SubscriptionOrm.expires_at > datetime.now(),
                )
            )
            return result.scalars().first()

    @staticmethod
    async def get_by_user(user_id: int) -> "SubscriptionOrm | None":
        """Последняя запись подписки пользователя."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm)
                .filter(SubscriptionOrm.user_id == user_id)
                .order_by(SubscriptionOrm.created_at.desc())
                .limit(1)
            )
            return result.scalars().first()

    @staticmethod
    async def activate(
        user_id: int,
        tier: SubscriptionTier,
        recurring_key: str | None = None,
        auto_renew: bool = True,
    ) -> "SubscriptionOrm":
        """Активировать/продлить подписку на 30 дней."""
        now = datetime.now()
        existing = await SubscriptionOrm.get_by_user(user_id)
        # Если есть активная — продлеваем expires_at
        if (
            existing
            and existing.status == SubscriptionStatus.ACTIVE
            and existing.expires_at
            and existing.expires_at > now
        ):
            async with async_session_factory() as session:
                sub = await session.get(SubscriptionOrm, existing.id)
                sub.tier = tier
                sub.status = SubscriptionStatus.ACTIVE
                sub.auto_renew = auto_renew
                if recurring_key:
                    sub.recurring_key = recurring_key
                sub.expires_at = existing.expires_at + timedelta(days=30)
                await session.commit()
                return sub
        # Новая подписка
        async with async_session_factory() as session:
            sub = SubscriptionOrm(
                user_id=user_id,
                tier=tier,
                status=SubscriptionStatus.ACTIVE,
                auto_renew=auto_renew,
                recurring_key=recurring_key,
                started_at=now,
                expires_at=now + timedelta(days=30),
            )
            session.add(sub)
            await session.commit()
            return sub

    @staticmethod
    async def cancel_auto_renew(user_id: int) -> bool:
        """Отмена автопродления (текущий период доигрывается до конца)."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm).filter(
                    SubscriptionOrm.user_id == user_id,
                    SubscriptionOrm.status == SubscriptionStatus.ACTIVE,
                )
            )
            sub = result.scalars().first()
            if sub is None:
                return False
            sub.auto_renew = False
            await session.commit()
            return True

    @staticmethod
    async def get_expiring_soon(days: int = 3) -> list["SubscriptionOrm"]:
        """Подписки, истекающие в течение N дней с включённым автопродлением."""
        now = datetime.now()
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm).filter(
                    SubscriptionOrm.status == SubscriptionStatus.ACTIVE,
                    SubscriptionOrm.auto_renew.is_(True),
                    SubscriptionOrm.expires_at > now,
                    SubscriptionOrm.expires_at <= now + timedelta(days=days),
                )
            )
            return result.scalars().all()

    @staticmethod
    async def get_active_for_renewal() -> list["SubscriptionOrm"]:
        """Активные с автопродлением, у которых срок истёк — продлеваем."""
        now = datetime.now()
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm).filter(
                    SubscriptionOrm.status == SubscriptionStatus.ACTIVE,
                    SubscriptionOrm.auto_renew.is_(True),
                    SubscriptionOrm.expires_at <= now,
                )
            )
            return result.scalars().all()

    @staticmethod
    async def expire_overdue() -> int:
        """Помечает истёкшие подписки как EXPIRED. Возвращает кол-во."""
        now = datetime.now()
        async with async_session_factory() as session:
            result = await session.execute(
                select(SubscriptionOrm).filter(
                    SubscriptionOrm.status == SubscriptionStatus.ACTIVE,
                    SubscriptionOrm.expires_at <= now,
                )
            )
            subs = result.scalars().all()
            for sub in subs:
                sub.status = SubscriptionStatus.EXPIRED
            await session.commit()
            return len(subs)
