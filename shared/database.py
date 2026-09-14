"""Движки и сессии SQLAlchemy 2 (async).

Используется только API-сервисом (src_fastapi/) и общими моделями.
Бот (src/) обращается к данным через HTTP-клиент к API, а не к БД напрямую —
кроме легаси-логики (work/rob/profile), которая до миграции на API ходит в БД.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from shared.config import get_settings

_settings = get_settings()

echo = _settings.ENV == "development" and False  # SQL-лог можно включить вручную

sync_engine = create_engine(url=_settings.DATABASE_URL_psycopg, echo=echo)
async_engine: AsyncEngine = create_async_engine(url=_settings.DATABASE_URL_asyncpg, echo=echo)

sync_session_factory = sessionmaker(sync_engine)
async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    __table_args__ = {"extend_existing": True}


async def get_async_session():
    """FastAPI dependency."""
    async with async_session_factory() as session:
        yield session
