from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from . import GroupUserOrm
from .imports import *


class MessageOrm(Base):
    __tablename__ = 'message'

    id: Mapped[int] = mapped_column(primary_key=True)
    group_user_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True)
    group_user: Mapped[GroupUserOrm] = relationship()
    text: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_message(group_user_id: int, text: str):
        async with async_session_factory() as session:
            new_message = MessageOrm(group_user_id=group_user_id, text=text)
            session.add(new_message)
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_messages(tg_chat_id: int):
        async with async_session_factory() as session:
            query = (
                select(MessageOrm)
                .join(MessageOrm.group_user)
                .filter(
                    GroupUserOrm.telegram_chat_id.__eq__(tg_chat_id)
                )
                .limit(10_000)
            )
            result = await session.execute(query)
            return result.scalars().all()
