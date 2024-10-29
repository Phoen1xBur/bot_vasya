from src.utils.enums import Rank

from .imports import *


class UserOrm(Base):
    __tablename__ = 'user'

    # id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rank: Mapped[Rank] = mapped_column(default=Rank.USER)

    @staticmethod
    async def insert_or_update_user(user_id: int, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(UserOrm)
                .filter(
                    UserOrm.user_id.__eq__(user_id)
                )
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
