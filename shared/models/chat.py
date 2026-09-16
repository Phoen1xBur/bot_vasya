
from datetime import datetime

from .imports import *


class TelegramChatOrm(Base):
    __tablename__ = "telegram_chat"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    answer_chance: Mapped[int] = mapped_column(default=5)
    ai_generate_text: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    @staticmethod
    async def insert_or_update_telegram_chat(chat_id: int, **kwargs) -> None:
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).filter(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            telegram_chat = result.scalars().first()
            if telegram_chat is None:
                session.add(TelegramChatOrm(chat_id=chat_id, **kwargs))
            else:
                for key, value in kwargs.items():
                    if hasattr(telegram_chat, key):
                        setattr(telegram_chat, key, value)
                    else:
                        raise AttributeError(f"Отсутствует атрибут {key}")
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_telegram_chat(chat_id: int) -> "TelegramChatOrm | None":
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).filter(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def get_chance(chat_id: int) -> "TelegramChatOrm | None":
        """Alias for get_telegram_chat (answer_chance lives on the row)."""
        return await TelegramChatOrm.get_telegram_chat(chat_id)

    @staticmethod
    async def change_answer_chance(chat_id: int, answer_chance: int) -> None:
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).filter(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            chat = result.scalars().first()
            if chat is None:
                chat = TelegramChatOrm(chat_id=chat_id, answer_chance=answer_chance)
                session.add(chat)
            else:
                chat.answer_chance = answer_chance
            await session.flush()
            await session.commit()

    @staticmethod
    async def change_ai_generate_text(chat_id: int, ai_generate_text: bool) -> None:
        async with async_session_factory() as session:
            query = select(TelegramChatOrm).filter(TelegramChatOrm.chat_id == chat_id)
            result = await session.execute(query)
            chat = result.scalars().first()
            if chat is None:
                chat = TelegramChatOrm(chat_id=chat_id, ai_generate_text=ai_generate_text)
                session.add(chat)
            else:
                chat.ai_generate_text = ai_generate_text
            await session.flush()
            await session.commit()
