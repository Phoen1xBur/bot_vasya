from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from . import GroupUserOrm
from .imports import *


class ProfessionOrm(Base):
    __tablename__ = 'profession'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class WorkActivityOrm(Base):
    __tablename__ = 'work_activity'

    id: Mapped[int] = mapped_column(primary_key=True)

    # Profession
    profession_id: Mapped[int] = mapped_column(ForeignKey('profession.id', ondelete='CASCADE'))
    profession: Mapped[ProfessionOrm] = relationship()
    # GroupUserOrm
    group_user_id: Mapped[int] = mapped_column(ForeignKey('group_user.id', ondelete='CASCADE'), index=True)
    group_user: Mapped[GroupUserOrm] = relationship()

    income: Mapped[int]  # Заработанный средства
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
