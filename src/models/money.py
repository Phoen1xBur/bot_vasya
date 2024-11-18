from datetime import datetime
from typing import Optional

from config import redis
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from utils.enums import TransactionType
from . import GroupUserOrm
from .imports import *

_second, _minute, _hour, _day = 1, 60, 3600, 86400  # Секунда, минута, час, сутки


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


class WorkActivityOrm(Base):
    __tablename__ = 'work_activity'

    id: Mapped[int] = mapped_column(primary_key=True)

    # Profession
    profession_id: Mapped[int] = mapped_column(ForeignKey('profession.id', ondelete='CASCADE'))
    profession: Mapped[ProfessionOrm] = relationship()
    # GroupUserOrm
    group_user_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True)
    group_user: Mapped[GroupUserOrm] = relationship()

    income: Mapped[int]  # Заработанный средства
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def get_all_work_activity() -> list["WorkActivityOrm"]:
        async with async_session_factory() as session:
            query = (
                select(WorkActivityOrm)
            )
            result = await session.execute(query)
            return result.scalars().all()

    @staticmethod
    async def get_last_work_activity_by_group_user_id(group_user_id: int) -> Optional["WorkActivityOrm"]:
        async with async_session_factory() as session:
            query = (
                select(WorkActivityOrm)
                .filter(WorkActivityOrm.group_user_id.__eq__(group_user_id))
                .order_by(WorkActivityOrm.created_at.desc())
                .limit(1)
            )
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def insert_work_activity(profession_id: int, group_user_id: int, income: int) -> None:
        async with async_session_factory() as session:
            work_activity = WorkActivityOrm(
                profession_id=profession_id,
                group_user_id=group_user_id,
                income=income,
            )
            session.add(work_activity)
            await session.flush()
            await session.commit()


class TransactionOrm(Base):
    __tablename__ = 'transaction'

    id: Mapped[int] = mapped_column(primary_key=True)

    # From GroupUserOrm
    group_user_from_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True, nullable=True)
    group_user_from: Mapped[GroupUserOrm] = relationship()
    # To GroupUserOrm
    group_user_to_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True, nullable=True)
    group_user_to: Mapped[GroupUserOrm] = relationship()

    transaction_type: Mapped[TransactionType]
    transferred_money: Mapped[int]  # total
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class Prison:
    __tablename = 'prison'
    __DEFAULT_IMPRISONMENT_TIME = _hour * 6
    _redis = redis

    def _get_table_name(self, chat_id: str | int, user_id: str | int) -> str:
        return f'{self.__tablename}_{chat_id}_{user_id}'

    def is_prisoner(self, chat_id: str | int, user_id: str | int) -> bool:
        table_name = self._get_table_name(chat_id, user_id)
        return self._redis.keys(table_name)

    def add_prisoner(self, chat_id: str | int, user_id: str | int, imprisonment_time: int = __DEFAULT_IMPRISONMENT_TIME) -> None:
        """Добавляет пользователя в тюрьму

        :param chat_id: id чата
        :param user_id: id пользователя
        :param imprisonment_time: время заключения в секундах, по умолчанию DEFAULT_IMPRISONMENT_TIME
        """
        table_name = self._get_table_name(chat_id, user_id)
        self._redis.set(table_name, 1, ex=imprisonment_time)


class Rob:
    pass
