from pyrogram.enums import ChatMemberStatus
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from . import UserOrm, TelegramChatOrm
from .imports import *


class GroupUserOrm(Base):
    __tablename__ = 'group_user'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id', ondelete='CASCADE'), index=True)
    user: Mapped[UserOrm] = relationship()
    telegram_chat_id: Mapped[int] = mapped_column(ForeignKey('telegram_chat.chat_id', ondelete='CASCADE'), index=True)
    telegram_chat: Mapped[TelegramChatOrm] = relationship()
    chat_member_status: Mapped[ChatMemberStatus]
    money: Mapped[int] = mapped_column(default=0)

    @staticmethod
    async def insert_or_update_group_user(user_id: int, tg_chat_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(GroupUserOrm)
                .filter(
                    GroupUserOrm.user_id.__eq__(user_id),
                    GroupUserOrm.telegram_chat_id.__eq__(tg_chat_id)
                )
            )
            result = await session.execute(query)
            group_user = result.scalars().first()
            if group_user is None:
                new_group_user = GroupUserOrm(
                    user_id=user_id, telegram_chat_id=tg_chat_id, **kwargs
                )
                session.add(new_group_user)
            else:
                for key, value in kwargs.items():
                    if hasattr(group_user, key):
                        setattr(group_user, key, value)
                    else:
                        raise AttributeError(f'Отсутствует атрибут {key}')
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_group_user(user_id: int, tg_chat_id: int):
        async with async_session_factory() as session:
            group_user = (
                select(GroupUserOrm)
                .filter(
                    GroupUserOrm.user_id.__eq__(user_id),
                    GroupUserOrm.telegram_chat_id.__eq__(tg_chat_id)
                )
            )
            res = await session.execute(group_user)
            return res.scalars().one_or_none()

    @staticmethod
    async def get_groups_user_by_telegram_chat_id(tg_chat_id: int) -> list["GroupUserOrm"]:
        async with async_session_factory() as session:
            groups_user = (
                select(GroupUserOrm)
                .filter(
                    GroupUserOrm.telegram_chat_id.__eq__(tg_chat_id),
                    GroupUserOrm.chat_member_status.notin_(
                        (
                            ChatMemberStatus.BANNED,
                            ChatMemberStatus.LEFT,
                        )
                    )
                )
            )
            res = await session.execute(groups_user)
            return res.scalars().all()
