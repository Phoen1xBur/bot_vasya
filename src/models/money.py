from datetime import datetime, timedelta
from typing import Optional

from config import redis
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from utils.enums import TransactionType
from .imports import *


class ProfessionOrm(Base):
    __tablename__ = 'profession'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    money_max: Mapped[int] = mapped_column(default=0)  # Максимальный порог заработка (Включительно)
    money_min: Mapped[int] = mapped_column(default=0)  # Минимальный порог заработка (Включительно)
    accompanying_text: Mapped[str] = mapped_column(nullable=True)

    @staticmethod
    async def get_all_profession() -> list["ProfessionOrm"]:
        async with async_session_factory() as session:
            query = (
                select(ProfessionOrm)
            )
            result = await session.execute(query)
            return result.scalars().all()


class TransactionOrm(Base):
    __tablename__ = 'transaction'

    id: Mapped[int] = mapped_column(primary_key=True)

    # From GroupUserOrm
    group_user_from_id: Mapped[int] = mapped_column(
        ForeignKey('group_user.id', ondelete='CASCADE'), index=True, nullable=True
    )
    # group_user_from: Mapped["GroupUserOrm"] = relationship()
    # To GroupUserOrm
    group_user_to_id: Mapped[int] = mapped_column(
        ForeignKey('group_user.id', ondelete='CASCADE'), index=True, nullable=True
    )
    # group_user_to: Mapped["GroupUserOrm"] = relationship()

    transaction_type: Mapped[TransactionType]
    transferred_money: Mapped[int]  # total
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_transaction(
            group_user_from_id: int | None, group_user_to_id: int | None,
            transaction_type: TransactionType, transferred_money: int
    ) -> None:
        async with async_session_factory() as session:
            transaction = TransactionOrm(
                group_user_from_id=group_user_from_id,
                group_user_to_id=group_user_to_id,
                transaction_type=transaction_type,
                transferred_money=transferred_money,
            )
            session.add(transaction)
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_all_transaction() -> list["TransactionOrm"]:
        async with async_session_factory() as session:
            query = (
                select(TransactionOrm)
            )
            result = await session.execute(query)
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
    __tablename = 'prison'
    _redis = redis

    @classmethod
    def _get_table_name(cls, chat_id: str | int, user_id: str | int) -> str:
        return f'{cls.__tablename}_{chat_id}_{user_id}'

    @classmethod
    def is_prisoner(cls, chat_id: str | int, user_id: str | int) -> bool:
        table_name = cls._get_table_name(chat_id, user_id)
        return cls._redis.keys(table_name)

    @classmethod
    def add_prisoner(cls, chat_id: str | int, user_id: str | int, imprisonment_time: int | timedelta) -> None:
        """Добавляет пользователя в тюрьму

        :param chat_id: id чата
        :param user_id: id пользователя
        :param imprisonment_time: время заключения в секундах
        """
        table_name = cls._get_table_name(chat_id, user_id)
        cls._redis.set(table_name, 1, ex=imprisonment_time)


class Rob:
    pass
