
from typing import Any

from shared.enums import Rank

from .imports import *


class UserOrm(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(nullable=True)
    last_name: Mapped[str] = mapped_column(nullable=True)
    username: Mapped[str] = mapped_column(nullable=True)
    rank: Mapped[Rank] = mapped_column(default=Rank.USER)


    @staticmethod
    async def get_by_username(username: str) -> "UserOrm | None":
        """Поиск пользователя по username (без @, case-insensitive)."""
        if not username:
            return None
        uname = username.strip().lstrip("@")
        if not uname:
            return None
        async with async_session_factory() as session:
            from sqlalchemy import func

            query = select(UserOrm).filter(func.lower(UserOrm.username) == uname.lower())
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def get_user_by_id(user_id: int) -> "UserOrm | None":
        async with async_session_factory() as session:
            query = select(UserOrm).filter(UserOrm.user_id == user_id)
            result = await session.execute(query)
            return result.scalars().first()

    @staticmethod
    async def insert_or_update_user(user_id: int, user: Any = None, **kwargs) -> None:
        """Upsert пользователя.

        `user` — любой объект с атрибутами first_name/last_name/username
        (aiogram.types.User или pyrogram.types.User). kwargs переопределяют поля.
        """
        async with async_session_factory() as session:
            query = select(UserOrm).filter(UserOrm.user_id == user_id)
            result = await session.execute(query)
            _user = result.scalars().first()

            def _attr(name: str):
                if name in kwargs and kwargs[name] is not None:
                    return kwargs[name]
                if user is None:
                    return None
                return getattr(user, name, None)

            fields = {
                "first_name": _attr("first_name"),
                "last_name": _attr("last_name"),
                "username": _attr("username"),
            }
            extra = {k: v for k, v in kwargs.items() if k not in fields}

            if _user is None:
                new_user = UserOrm(user_id=user_id, **fields, **extra)
                session.add(new_user)
            else:
                for key, value in {**fields, **extra}.items():
                    if value is None and key in fields:
                        if user is None and key not in kwargs:
                            continue
                    if hasattr(_user, key):
                        setattr(_user, key, value)
                    else:
                        raise AttributeError(f"Отсутствует атрибут {key}")
            await session.flush()
            await session.commit()
