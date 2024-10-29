from datetime import datetime

from .imports import *


class TelegramChatOrm(Base):
    __tablename__ = 'telegram_chat'

    # id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    answer_chance: Mapped[int] = mapped_column(default=5)
    # время создания группы
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_or_update_telegram_chat(chat_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(TelegramChatOrm)
                .filter(
                    TelegramChatOrm.chat_id.__eq__(chat_id)
                )
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
            query = (
                select(TelegramChatOrm)
                .filter(
                    TelegramChatOrm.chat_id.__eq__(chat_id)
                )
            )
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def change_answer_chance(chat_id: int, answer_chance: int):
        async with async_session_factory() as session:
            query = (
                select(TelegramChatOrm)
                .filter(
                    TelegramChatOrm.chat_id.__eq__(chat_id)
                )
            )
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
            query = (
                select(TelegramChatOrm)
                .filter(
                    TelegramChatOrm.chat_id.__eq__(chat_id)
                )
            )
            result = await session.execute(query)
            return result.scalars().first()
