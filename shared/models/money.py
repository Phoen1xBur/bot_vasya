
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from shared.config import get_settings
from shared.enums import TransactionType
from .imports import *


class ProfessionOrm(Base):
    __tablename__ = "profession"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    money_max: Mapped[int] = mapped_column(default=0)
    money_min: Mapped[int] = mapped_column(default=0)
    accompanying_text: Mapped[str] = mapped_column(nullable=True)

    @staticmethod
    async def get_all_profession() -> list["ProfessionOrm"]:
        async with async_session_factory() as session:
            query = select(ProfessionOrm)
            result = await session.execute(query)
            return result.scalars().all()


class TransactionOrm(Base):
    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_user_from_id: Mapped[int] = mapped_column(
        ForeignKey("group_user.id", ondelete="CASCADE"), index=True, nullable=True
    )
    group_user_to_id: Mapped[int] = mapped_column(
        ForeignKey("group_user.id", ondelete="CASCADE"), index=True, nullable=True
    )
    transaction_type: Mapped[TransactionType]
    transferred_money: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_transaction(
        group_user_from_id: int | None,
        group_user_to_id: int | None,
        transaction_type: TransactionType,
        transferred_money: int,
    ) -> None:
        async with async_session_factory() as session:
            session.add(
                TransactionOrm(
                    group_user_from_id=group_user_from_id,
                    group_user_to_id=group_user_to_id,
                    transaction_type=transaction_type,
                    transferred_money=transferred_money,
                )
            )
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_all_transaction() -> list["TransactionOrm"]:
        async with async_session_factory() as session:
            result = await session.execute(select(TransactionOrm))
            return result.scalars().all()

    @staticmethod
    async def get_last_transaction_by_params(**kwargs) -> Optional["TransactionOrm"]:
        async with async_session_factory() as session:
            query = (
                select(TransactionOrm)
                .filter_by(**kwargs)
                .order_by(TransactionOrm.created_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            return result.scalars().first()


class Prison:
    """Тюрьма — в Redis с TTL (автоочистка)."""

    __tablename = "prison"
    _redis = None

    @classmethod
    def _redis_client(cls):
        if cls._redis is None:
            import redis as redis_package

            cls._redis = redis_package.Redis(**get_settings().REDIS_CREDENTIALS)
        return cls._redis

    @classmethod
    def _get_table_name(cls, chat_id: str | int, user_id: str | int) -> str:
        return f"{cls.__tablename}_{chat_id}_{user_id}"

    @classmethod
    def is_prisoner(cls, chat_id: str | int, user_id: str | int) -> tuple[Any, int]:
        table_name = cls._get_table_name(chat_id, user_id)
        r = cls._redis_client()
        return r.keys(table_name), r.ttl(table_name)

    @classmethod
    def add_prisoner(
        cls, chat_id: str | int, user_id: str | int, imprisonment_time: int | timedelta
    ) -> None:
        table_name = cls._get_table_name(chat_id, user_id)
        r = cls._redis_client()
        r.set(table_name, 1, ex=imprisonment_time)

    @classmethod
    def free_prisoner(cls, chat_id: str | int, user_id: str | int) -> bool:
        """Досрочное освобождение. Возвращает True, если был в тюрьме."""
        table_name = cls._get_table_name(chat_id, user_id)
        r = cls._redis_client()
        deleted = r.delete(table_name)
        return bool(deleted)


class Rob:
    pass
