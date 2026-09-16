"""SQLAlchemy Enum helpers: store Python enum *values* as VARCHAR (no PG ENUM type).

Commercialization migrations created String columns; ORM Mapped[Enum] would otherwise
emit native PostgreSQL ENUMs (e.g. subscriptionstatus) and blow up at runtime.
"""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Type

from sqlalchemy import Enum as SAEnum


def str_enum(enum_cls: Type[PyEnum], **kwargs):
    """VARCHAR-backed enum using ``enum.value`` (not member name)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        values_callable=lambda members: [m.value for m in members],
        **kwargs,
    )
