
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, Integer, DateTime, JSON, ForeignKey, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base, async_session_factory
from shared.enums import GameRoomStatus, GameType
from shared.sa_enum import str_enum


class GameRoomOrm(Base):
    """Комната мини-игры.

    Дублируется в Redis с TTL (GAME_ROOM_TTL_MINUTES) для автоочистки.
    """

    __tablename__ = "game_room"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_type: Mapped[GameType] = mapped_column(str_enum(GameType), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)  # чат-источник
    initiator_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # для дуэли
    status: Mapped[GameRoomStatus] = mapped_column(str_enum(GameRoomStatus), default=GameRoomStatus.WAITING, index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    bet: Mapped[int] = mapped_column(Integer, default=0)  # ставка в васякоинах
    winner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    @staticmethod
    async def create(
        game_type: GameType,
        chat_id: int,
        initiator_id: int,
        target_id: int | None = None,
        bet: int = 0,
        ttl_minutes: int = 15,
    ) -> "GameRoomOrm":
        try:
            await GameRoomOrm.expire_overdue()
        except Exception:
            pass
        now = datetime.now()
        from datetime import timedelta

        async with async_session_factory() as session:
            room = GameRoomOrm(
                game_type=game_type,
                chat_id=chat_id,
                initiator_id=initiator_id,
                target_id=target_id,
                bet=bet,
                expires_at=now + timedelta(minutes=ttl_minutes),
                state={},
            )
            session.add(room)
            await session.commit()
            await session.refresh(room)
            return room


    @staticmethod
    def _as_uuid(room_id: str | uuid.UUID) -> uuid.UUID:
        return room_id if isinstance(room_id, uuid.UUID) else uuid.UUID(str(room_id))

    @staticmethod
    async def get(room_id: str | uuid.UUID) -> "GameRoomOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(
                select(GameRoomOrm).filter(GameRoomOrm.id == GameRoomOrm._as_uuid(room_id))
            )
            return result.scalars().first()

    @staticmethod
    async def update(room_id: str | uuid.UUID, **kwargs) -> "GameRoomOrm | None":
        async with async_session_factory() as session:
            result = await session.execute(
                select(GameRoomOrm).filter(GameRoomOrm.id == GameRoomOrm._as_uuid(room_id))
            )
            room = result.scalars().first()
            if room is None:
                return None
            for k, v in kwargs.items():
                if hasattr(room, k):
                    setattr(room, k, v)
            await session.commit()
            return room

    @staticmethod
    async def get_active_for_user(user_id: int) -> "GameRoomOrm | None":
        """Активная комната, где пользователь участник."""
        try:
            await GameRoomOrm.expire_overdue()
        except Exception:
            pass
        async with async_session_factory() as session:
            result = await session.execute(
                select(GameRoomOrm).filter(
                    GameRoomOrm.status.in_([GameRoomStatus.WAITING, GameRoomStatus.ACTIVE]),
                    GameRoomOrm.expires_at > datetime.now(),
                    (GameRoomOrm.initiator_id == user_id)
                    | (GameRoomOrm.target_id == user_id),
                )
            )
            return result.scalars().first()

    @staticmethod
    async def expire_overdue() -> int:
        now = datetime.now()
        async with async_session_factory() as session:
            result = await session.execute(
                select(GameRoomOrm).filter(
                    GameRoomOrm.status.in_([GameRoomStatus.WAITING, GameRoomStatus.ACTIVE]),
                    GameRoomOrm.expires_at <= now,
                )
            )
            rooms = list(result.scalars().all())
            snapshots = [(str(r.id), r.status) for r in rooms]
            for r in rooms:
                r.status = GameRoomStatus.EXPIRED
            await session.commit()

        if snapshots:
            try:
                from shared.game_stakes import refund_room_stakes

                for rid, prior_status in snapshots:
                    room = await GameRoomOrm.get(rid)
                    if room is None:
                        continue
                    try:
                        await refund_room_stakes(room, status_override=prior_status)
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception(
                            "expire refund failed room=%s", rid
                        )
            except Exception:
                import logging
                logging.getLogger(__name__).exception("expire refund import/loop failed")
        return len(snapshots)


class GameParticipantOrm(Base):
    """Участники массовых игр (рулетка)."""

    __tablename__ = "game_participant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("game_room.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    bet: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
