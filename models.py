from sqlalchemy import select, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, async_session_factory


class Messages(Base):
    __tablename__ = 'messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str]

    @staticmethod
    async def insert_message(telegram_chat_id: int, text: str):
        async with async_session_factory() as session:
            new_message = Messages(telegram_chat_id=telegram_chat_id, text=text)
            session.add(new_message)
            await session.flush()
            await session.commit()

    @staticmethod
    async def get_messages(telegram_channel_id: int):
        async with async_session_factory() as session:
            query = select(Messages).where(Messages.telegram_chat_id == telegram_channel_id)
            result = await session.execute(query)
            return result.scalars().all()


class ChatGroupSettings(Base):
    __tablename__ = 'chat_group_settings'

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger)

    answer_chance: Mapped[int] = mapped_column(default=5)

    @staticmethod
    async def change_answer_chance(group_id: int, answer_chance: int):
        async with async_session_factory() as session:
            query = select(ChatGroupSettings).where(ChatGroupSettings.group_id == group_id)
            result = await session.execute(query)
            chat_group_settings = result.scalars().first()
            if chat_group_settings is None:
                chat_group_settings = ChatGroupSettings(group_id=group_id, answer_chance=answer_chance)
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
            query = select(ChatGroupSettings).where(ChatGroupSettings.group_id == group_id)
            result = await session.execute(query)
            return result.scalars().first()
