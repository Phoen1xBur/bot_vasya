"""Общий импорт для моделей — чтобы не дублировать."""
from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory
