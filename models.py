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
