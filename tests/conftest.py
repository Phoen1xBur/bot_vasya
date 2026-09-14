"""Общие фикстуры для тестов.

БД: in-memory SQLite (StaticPool, одна связь на весь процесс), чтобы
таблицы создавались один раз и были видны во всех сессиях. Сессия-фабрика
patch'ится в shared.database и подхватывается всеми моделями (они делают
`from shared.database import async_session_factory` уже после патча).

ENV задаётся ДО импорта shared.*, чтобы get_settings() вернул тестовые
значения и shared.database не пытался создать postgres-движки.
"""
import os

# --- Окружение ДО любого импорта shared.* ---
os.environ.setdefault("TOKEN", "123:test:token")
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "testhash")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("ADMIN_IDS", "[111111,222222]")
os.environ.setdefault("AI_API_KEY", "test-ai-key")
os.environ.setdefault("TBANK_TERMINAL_ID", "test_terminal")
os.environ.setdefault("TBANK_TERMINAL_PASSWORD", "test_password")

import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import shared.database as db  # noqa: E402  — импорт после env; создаются sqlite-движки
from shared.database import Base  # noqa: E402

# Одна in-memory БД на процесс (StaticPool держит одно соединение).
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
_test_session_factory = async_sessionmaker(_test_engine, expire_on_commit=False)

# Патчим центральный модуль БД — все модели подхватят тестовую фабрику,
# т.к. импортируют `async_session_factory` позже этого присвоения.
db.async_engine = _test_engine
db.async_session_factory = _test_session_factory

# Импортируем модели (теперь с patch'ем) и собираем таблицы для тестов.
from shared.models.ad_campaign import AdCampaignOrm, ChatUniqueUsersOrm  # noqa: E402
from shared.models.donation import DonationOrm  # noqa: E402
from shared.models.game_room import GameParticipantOrm, GameRoomOrm  # noqa: E402
from shared.models.order import OrderOrm  # noqa: E402
from shared.models.payment import PaymentOrm  # noqa: E402
from shared.models.subscription import SubscriptionOrm  # noqa: E402

_TEST_TABLES = [
    PaymentOrm.__table__,
    SubscriptionOrm.__table__,
    DonationOrm.__table__,
    OrderOrm.__table__,
    AdCampaignOrm.__table__,
    ChatUniqueUsersOrm.__table__,
    GameRoomOrm.__table__,
    GameParticipantOrm.__table__,
]


@pytest_asyncio.fixture
async def db():
    """Создаёт таблицы перед тестом, дропает после — изоляция между тестами."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=_TEST_TABLES)
        )
    try:
        yield
    finally:
        async with _test_engine.begin() as conn:
            await conn.run_sync(
                lambda c: Base.metadata.drop_all(c, tables=_TEST_TABLES)
            )
