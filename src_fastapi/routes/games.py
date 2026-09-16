"""Роутер мини-игр: создание/вход/действие/отмена комнат.

Валидация initData в каждом эндпоинте. Проверка участников для дуэли.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from shared.config import get_settings
from shared.enums import GameRoomStatus, GameType
from shared.models.game_room import GameRoomOrm
from src_fastapi.deps import require_telegram_user
from src_fastapi.services import games as game_service

logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(prefix="/api/games", tags=["Игры"])


@router.post("/rooms")
async def create_room(body: dict = Body(...), profile: dict = Depends(require_telegram_user)):
    """Создать комнату.

    body: {game_type: "ttt"|"roulette"|"slots", chat_id, target_id?, bet}
    """
    game_type_str = body.get("game_type", "")
    try:
        game_type = GameType(game_type_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный тип игры")

    chat_id = int(body.get("chat_id", 0))
    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail="Не указан chat_id — откройте игру из группового чата (кнопка мини-игр)",
        )

    bet = int(body.get("bet", 0))
    target_id = body.get("target_id")

    # Проверка, что нет активной комнаты (для рулетки — вернём существующую в том же чате)
    existing = await GameRoomOrm.get_active_for_user(profile["id"])
    if existing:
        if (
            game_type == GameType.ROULETTE
            and existing.game_type == GameType.ROULETTE
            and int(existing.chat_id) == int(chat_id)
        ):
            return await game_service.get_room_state_view(existing)
        # Смена мини-игры / залипшая комната — закрываем старую и создаём новую
        if existing.game_type != game_type or int(existing.chat_id) != int(chat_id):
            await GameRoomOrm.update(str(existing.id), status=GameRoomStatus.CANCELLED)
        else:
            raise HTTPException(status_code=409, detail="У вас уже есть активная игра")

    # Для TTT нужен target_id
    if game_type == GameType.TTT and not target_id:
        raise HTTPException(
            status_code=400,
            detail="Для дуэли выберите соперника (target_id) до создания комнаты",
        )

    # Списываем ставку сразу (если есть)
    if bet > 0:
        from shared.models.group_user import GroupUserOrm

        group_user = await GroupUserOrm.get_group_user(profile["id"], chat_id)
        if group_user is None or group_user.money < bet:
            raise HTTPException(status_code=400, detail="Недостаточно васякоинов для ставки")
        await group_user.money_minus(bet)

    room = await GameRoomOrm.create(
        game_type=game_type,
        chat_id=chat_id,
        initiator_id=profile["id"],
        target_id=int(target_id) if target_id else None,
        bet=bet,
        ttl_minutes=_settings.GAME_ROOM_TTL_MINUTES,
    )

    # Для TTT инициализируем поле
    if game_type == GameType.TTT:
        await GameRoomOrm.update(str(room.id), state={"board": " " * 9, "turn": "X"})

    # Дублируем в Redis с TTL для быстрого доступа и автоочистки
    r = __import__("shared.redis_client", fromlist=["get_redis"]).get_redis()
    r.setex(
        f"game:room:{room.id}",
        _settings.GAME_ROOM_TTL_MINUTES * 60,
        str(room.id),
    )

    return await game_service.get_room_state_view(await GameRoomOrm.get(str(room.id)))


@router.get("/rooms/{room_id}")
async def get_room(room_id: str, profile: dict = Depends(require_telegram_user)):
    """Состояние комнаты."""
    room = await GameRoomOrm.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    # Проверка не истекла ли
    if room.status in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        from datetime import datetime

        if room.expires_at and room.expires_at < datetime.now():
            await GameRoomOrm.update(room_id, status=GameRoomStatus.EXPIRED)
            raise HTTPException(status_code=410, detail="Комната истекла")
    view = await game_service.get_room_state_view(room)
    return JSONResponse(content=view, headers={"Cache-Control": "no-store"})


@router.post("/rooms/{room_id}/join")
async def join_room(
    room_id: str,
    body: dict = Body(default=None),
    profile: dict = Depends(require_telegram_user),
):
    """Присоединиться к комнате (рулетка) / принять дуэль (TTT)."""
    room = await GameRoomOrm.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    user_id = profile["id"]

    if room.game_type == GameType.TTT:
        # Дуэль: принять может только target_id
        if room.target_id != user_id:
            raise HTTPException(status_code=403, detail="Эта дуэль не для вас")
        if room.status != GameRoomStatus.WAITING:
            raise HTTPException(status_code=400, detail="Дуэль уже начата или завершена")
        # Списываем ставку target'а
        bet = room.bet
        if bet > 0:
            from shared.models.group_user import GroupUserOrm

            group_user = await GroupUserOrm.get_group_user(user_id, room.chat_id)
            if group_user is None or group_user.money < bet:
                raise HTTPException(status_code=400, detail="Недостаточно васякоинов для ставки")
            await group_user.money_minus(bet)
        await GameRoomOrm.update(room_id, status=GameRoomStatus.ACTIVE)
    else:
        # Рулетка
        bet = int((body or {}).get("bet", 0))
        if bet <= 0:
            raise HTTPException(status_code=400, detail="Укажите ставку")
        try:
            await game_service.roulette_join(room, user_id, bet)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return await game_service.get_room_state_view(await GameRoomOrm.get(room_id))


@router.post("/rooms/{room_id}/action")
async def game_action(
    room_id: str,
    body: dict = Body(...),
    profile: dict = Depends(require_telegram_user),
):
    """Ход/действие в игре. body: {action: {...}}"""
    room = await GameRoomOrm.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    user_id = profile["id"]
    action = body.get("action", body)

    try:
        if room.game_type == GameType.TTT:
            result = await game_service.ttt_action(room, user_id, action)
        elif room.game_type == GameType.ROULETTE:
            result = await game_service.roulette_spin(room, user_id, action)
        elif room.game_type == GameType.SLOTS:
            result = await game_service.slots_spin(room, user_id, action)
        else:
            raise HTTPException(status_code=400, detail="Неизвестный тип игры")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rooms/{room_id}/cancel")
async def cancel_room(room_id: str, profile: dict = Depends(require_telegram_user)):
    """Отменить комнату (только создатель)."""
    room = await GameRoomOrm.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if room.initiator_id != profile["id"] and profile["id"] not in _settings.ADMIN_ID_SET:
        raise HTTPException(status_code=403, detail="Отменить может только создатель")
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise HTTPException(status_code=400, detail="Комната уже завершена")

    # Возврат ставки
    if room.bet > 0:
        from shared.models.group_user import GroupUserOrm

        group_user = await GroupUserOrm.get_group_user(room.initiator_id, room.chat_id)
        if group_user:
            await group_user.money_plus(room.bet)

    await GameRoomOrm.update(room_id, status=GameRoomStatus.CANCELLED)
    return {"ok": True, "status": "cancelled"}
