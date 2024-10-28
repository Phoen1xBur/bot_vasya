from datetime import datetime

from pyrogram.enums.chat_member_status import ChatMemberStatus
from sqlalchemy import ForeignKey, select, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base, async_session_factory
from utils.enums import Rank


class UserOrm(Base):
    __tablename__ = 'user'

    # id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rank: Mapped[Rank] = mapped_column(default=Rank.USER)

    @staticmethod
    async def insert_user(user_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(UserOrm)
                .filter(UserOrm.user_id == user_id)
            )
            result = await session.execute(query)
            user = result.scalars().first()
            if user is None:
                new_user = UserOrm(
                    user_id=user_id, **kwargs
                )
                session.add(new_user)
            else:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                    else:
                        raise AttributeError(f'Отсутствует атрибут {key}')
            await session.flush()
            await session.commit()


class TelegramChatOrm(Base):
    __tablename__ = 'telegram_chat'

    # id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    answer_chance: Mapped[int] = mapped_column(default=5)
    # время создания группы
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_telegram_chat(chat_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(TelegramChatOrm)
                .filter(TelegramChatOrm.chat_id == chat_id)
            )
            result = await session.execute(query)
            telegram_chat = result.scalars().first()
            if telegram_chat is None:
                new_telegram_chat = TelegramChatOrm(
                    chat_id=chat_id, **kwargs
                )
                session.add(new_telegram_chat)
            else:
                for key, value in kwargs.items():
                    if hasattr(telegram_chat, key):
                        setattr(telegram_chat, key, value)
                    else:
                        raise AttributeError(f'Отсутствует атрибут {key}')
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_telegram_chat(chat_id: int):
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).where(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def change_answer_chance(chat_id: int, answer_chance: int):
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).where(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            chat_group_settings = result.scalars().first()
            if chat_group_settings is None:
                chat_group_settings = TelegramChatOrm(chat_id=chat_id, answer_chance=answer_chance)
                session.add(chat_group_settings)
                await session.flush()
                await session.commit()
            else:
                chat_group_settings.answer_chance = answer_chance
                await session.flush()
                await session.commit()

    @staticmethod
    async def get_chance(chat_id: int):
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).where(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            return result.scalars().first()


class GroupUserOrm(Base):
    __tablename__ = 'group_user'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.user_id', ondelete='CASCADE'), index=True)
    user: Mapped["UserOrm"] = relationship()
    telegram_chat_id: Mapped[int] = mapped_column(ForeignKey('telegram_chat.chat_id', ondelete='CASCADE'), index=True)
    telegram_chat: Mapped["TelegramChatOrm"] = relationship()
    chat_member_status: Mapped[ChatMemberStatus]
    money: Mapped[int] = mapped_column(default=0)

    @staticmethod
    # async def insert_group_user(user_id: int, tg_chat_id: int, chat_member_status: ChatMemberStatus):
    async def insert_group_user(user_id: int, tg_chat_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(GroupUserOrm)
                .filter(GroupUserOrm.user_id == user_id)
                .filter(GroupUserOrm.telegram_chat_id == tg_chat_id)
            )
            result = await session.execute(query)
            group_user = result.scalars().first()
            if group_user is None:
                new_group_user = GroupUserOrm(
                    # user_id=user_id, telegram_chat_id=tg_chat_id, chat_member_status=chat_member_status
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
                    GroupUserOrm.user_id == user_id,
                    GroupUserOrm.telegram_chat_id == tg_chat_id
                )
            )
            res = await session.execute(group_user)
            return res.scalars().one_or_none()

    async def set_money(self, money: int):
        async with async_session_factory() as session:
            self.money = money
            await session.commit()

    async def set_chat_member_status(self, chat_member_status: ChatMemberStatus):
        async with async_session_factory() as session:
            self.chat_member_status = chat_member_status
            await session.commit()


class MessageOrm(Base):
    __tablename__ = 'message'
    id: Mapped[int] = mapped_column(primary_key=True)
    group_user_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True)
    group_user: Mapped["GroupUserOrm"] = relationship()
    text: Mapped[str]

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
            query = select(MessageOrm).join(MessageOrm.group_user).filter(GroupUserOrm.telegram_chat_id == tg_chat_id)
            result = await session.execute(query)
            return result.scalars().all()


if __name__ == '__main__':
    from utils.db import create_tables
    create_tables()
