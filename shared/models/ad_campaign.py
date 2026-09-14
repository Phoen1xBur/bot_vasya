
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, Float, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory
from shared.enums import AdCampaignStatus


class AdCampaignOrm(Base):
    """Рекламная кампания."""

    __tablename__ = "ad_campaign"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advertiser_id: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(String(4096))
    link: Mapped[str] = mapped_column(String(1024))
    target_unique_users: Mapped[int] = mapped_column(Integer)  # запрошенные у.п.
    selected_chats: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    price: Mapped[int] = mapped_column(Integer, default=0)  # копейки
    status: Mapped[AdCampaignStatus] = mapped_column(default=AdCampaignStatus.DRAFT, index=True)
    # Результат AI-проверки: {"approved": bool, "reason": str, "risk_level": str}
    ai_verdict: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    admin_comment: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Реальный охват у.п. после показа
    actual_reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @staticmethod
    async def create(**kwargs) -> "AdCampaignOrm":
        async with async_session_factory() as session:
            c = AdCampaignOrm(**kwargs)
            session.add(c)
            await session.commit()
            return c

    @staticmethod
    async def get_by_id(campaign_id: int) -> "AdCampaignOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(select(AdCampaignOrm).filter(AdCampaignOrm.id == campaign_id))
            return result.scalars().first()

    @staticmethod
    async def list_by_status(status: AdCampaignStatus | None = None) -> list["AdCampaignOrm"]:
        async with async_session_factory() as session:
            q = select(AdCampaignOrm)
            if status is not None:
                q = q.filter(AdCampaignOrm.status == status)
            q = q.order_by(AdCampaignOrm.created_at.desc())
            result = await session.execute(q)
            return result.scalars().all()

    @staticmethod
    async def update(campaign_id: int, **kwargs) -> "AdCampaignOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(select(AdCampaignOrm).filter(AdCampaignOrm.id == campaign_id))
            c = result.scalars().first()
            if c is None:
                return None
            for k, v in kwargs.items():
                if hasattr(c, k):
                    setattr(c, k, v)
            await session.commit()
            return c


class ChatUniqueUsersOrm(Base):
    """Кэш уникальных пользователей по чатам для таргетинга рекламы.

    Обновляется по событиям входа/выхода участников (или раз в сутки).
    """

    __tablename__ = "chat_unique_users"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    unique_user_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # множество user_id
    members_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @staticmethod
    async def upsert(chat_id: int, user_ids: list[int]) -> "ChatUniqueUsersOrm":
        async with async_session_factory() as session:
            result = await session.execute(
                select(ChatUniqueUsersOrm).filter(ChatUniqueUsersOrm.chat_id == chat_id)
            )
            row = result.scalars().first()
            if row is None:
                row = ChatUniqueUsersOrm(
                    chat_id=chat_id,
                    unique_user_ids=sorted(set(user_ids)),
                    members_count=len(set(user_ids)),
                )
                session.add(row)
            else:
                row.unique_user_ids = sorted(set(user_ids))
                row.members_count = len(set(user_ids))
            await session.commit()
            return row

    @staticmethod
    async def get_all() -> list["ChatUniqueUsersOrm"]:
        async with async_session_factory() as session:
            result = await session.execute(select(ChatUniqueUsersOrm))
            return result.scalars().all()

    @staticmethod
    async def get(chat_id: int) -> "ChatUniqueUsersOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(
                select(ChatUniqueUsersOrm).filter(ChatUniqueUsersOrm.chat_id == chat_id)
            )
            return result.scalars().first()
