import pyrogram

from utils.enums import Rank

from .imports import *


class UserOrm(Base):
    __tablename__ = 'user'

    # id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    username: Mapped[str] = mapped_column(nullable=True)
    rank: Mapped[Rank] = mapped_column(default=Rank.USER)

    @staticmethod
    async def insert_or_update_user(user_id: int, user: pyrogram.types.User = None, **kwargs):
        async with async_session_factory() as session:
            query = (
                select(UserOrm)
                .filter(
                    UserOrm.user_id.__eq__(user_id)
                )
            )
            result = await session.execute(query)
            _user = result.scalars().first()
            if _user is None:
                new_user = UserOrm(
                    user_id=user_id,
                    first_name=None if user is None else user.first_name,
                    last_name=None if user is None else user.last_name,
                    username=None if user is None else user.username,
                    **kwargs
                )
                session.add(new_user)
            else:
                _user.first_name = None if user is None else user.first_name
                _user.last_name = None if user is None else user.last_name
                _user.username = None if user is None else user.username
                for key, value in kwargs.items():
                    if hasattr(_user, key):
                        setattr(_user, key, value)
                    else:
                        raise AttributeError(f'Отсутствует атрибут {key}')
            await session.flush()
            await session.commit()
