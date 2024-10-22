import asyncio

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from config import settings

echo = False

sync_engine = create_engine(
    url=settings.DATABASE_URL_psycopg,
    echo=echo
)

async_engine = create_async_engine(
    url=settings.DATABASE_URL_asyncpg,
    echo=echo
)

async_session_factory = async_sessionmaker(async_engine)


class Base(DeclarativeBase):
    pass

# Sync variant
# with engine.connect() as conn:
#     query = text("SELECT VERSION()")
#     res = conn.execute(query)
#     print(f'{res.first()=}')
#
#
# # Async variant
# async def get_version():
#     async with async_engine.connect() as conn:
#         query = text("SELECT VERSION()")
#         res = await conn.execute(query)
#         print(f'{res.first()=}')
#
#
# asyncio.run(get_version())
