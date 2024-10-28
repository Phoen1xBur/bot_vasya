from datetime import datetime
from typing import Optional

from aiogram.enums.chat_member_status import ChatMemberStatus
from sqlalchemy import ForeignKey, select, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, async_session_factory
from utils.enums import Rank


class User(Base):
    __tablename__ = 'user'
    id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    rank = mapped_column(Rank, default=Rank.USER, nullable=False)

    @staticmethod
    async def insert_user(user_id: int, rank: Rank = Rank.USER):
        async with async_session_factory() as session:
            user = User(id=user_id, rank=rank)
            session.add(user)
            await session.commit()


class GroupUser(Base):
    __tablename__ = 'group_user'
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('user.id', ondelete='SET NULL'), index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_member_status: Mapped[ChatMemberStatus]
    money: Mapped[int] = mapped_column(default=0)

    @staticmethod
    async def insert_group_user(telegram_chat_id: int, user: int, chat_member_status: ChatMemberStatus):
        async with async_session_factory() as session:
            new_group_user = GroupUser(telegram_chat_id=telegram_chat_id, user=user, chat_member_status=chat_member_status)
            session.add(new_group_user)
            await session.flush()
            await session.commit()

    async def set_money(self, money: int):
        async with async_session_factory() as session:
            self.money = money
            await session.commit()

    async def set_chat_member_status(self, chat_member_status: ChatMemberStatus):
        async with async_session_factory() as session:
            self.chat_member_status = chat_member_status
            await session.commit()


class Message(Base):
    __tablename__ = 'message'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)

    @staticmethod
    async def insert_message(telegram_chat_id: int, text: str):
        async with async_session_factory() as session:
            new_message = Message(telegram_chat_id=telegram_chat_id, text=text)
            session.add(new_message)
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_messages(telegram_channel_id: int):
        async with async_session_factory() as session:
            query = select(Message).where(Message.telegram_chat_id == telegram_channel_id)
            result = await session.execute(query)
            return result.scalars().all()


class TelegramChat(Base):
    __tablename__ = 'telegram_chat'

    id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    answer_chance: Mapped[int] = mapped_column(default=5)
    # время создания группы
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def change_answer_chance(group_id: int, answer_chance: int):
        async with async_session_factory() as session:
            query = select(TelegramChat).where(TelegramChat.id == group_id)
            result = await session.execute(query)
            chat_group_settings = result.scalars().first()
            if chat_group_settings is None:
                chat_group_settings = TelegramChat(id=group_id, answer_chance=answer_chance)
                session.add(chat_group_settings)
                await session.flush()
                await session.commit()
            else:
                chat_group_settings.answer_chance = answer_chance
                await session.flush()
                await session.commit()

    @staticmethod
    async def get_chance(group_id: int):
        async with async_session_factory() as session:
            query = select(TelegramChat).where(TelegramChat.id == group_id)
            result = await session.execute(query)
            return result.scalars().first()
