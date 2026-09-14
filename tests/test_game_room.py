"""Тесты мини-игр: комнаты (создание/проверка/истечение) и логика хода (TTT)."""
import types
import uuid
from datetime import datetime, timedelta

import pytest

import src_fastapi.services.games as game_service
from shared.database import async_session_factory
from shared.enums import GameRoomStatus, GameType
from shared.models.game_room import GameRoomOrm


# ----------------- Комнаты (БД) -----------------


async def test_create_and_get_room(db):
    room = await GameRoomOrm.create(
        GameType.TTT, chat_id=1, initiator_id=10, target_id=20, bet=0, ttl_minutes=15
    )
    assert room.id is not None

    fetched = await GameRoomOrm.get(str(room.id))
    assert fetched is not None
    assert fetched.initiator_id == 10
    assert fetched.target_id == 20
    assert fetched.status == GameRoomStatus.WAITING


async def test_update_room(db):
    room = await GameRoomOrm.create(GameType.TTT, 1, 10, 20)
    await GameRoomOrm.update(str(room.id), status=GameRoomStatus.ACTIVE, state={"board": " " * 9, "turn": "X"})
    fetched = await GameRoomOrm.get(str(room.id))
    assert fetched.status == GameRoomStatus.ACTIVE
    assert fetched.state["turn"] == "X"


async def test_expire_overdue_rooms(db):
    room = await GameRoomOrm.create(GameType.TTT, 1, 10, 20, ttl_minutes=15)
    async with async_session_factory() as session:
        r = await session.get(GameRoomOrm, room.id)
        r.expires_at = datetime.now() - timedelta(minutes=1)
        await session.commit()

    n = await GameRoomOrm.expire_overdue()
    assert n >= 1
    r2 = await GameRoomOrm.get(str(room.id))
    assert r2.status == GameRoomStatus.EXPIRED


async def test_get_active_for_user(db):
    await GameRoomOrm.create(GameType.TTT, 1, 777, 888, ttl_minutes=15)
    found = await GameRoomOrm.get_active_for_user(777)
    assert found is not None
    assert found.initiator_id == 777
    # посторонний — не находит
    assert await GameRoomOrm.get_active_for_user(999999) is None


# ----------------- Логика крестики-нолики -----------------


def test_check_winner_rows():
    assert game_service._check_winner("XXX      ") == "X"
    assert game_service._check_winner("   OOO   ") == "O"
    assert game_service._check_winner("      XXX") == "X"


def test_check_winner_columns():
    assert game_service._check_winner("O  O  O  ") == "O"
    assert game_service._check_winner(" X  X  X ") == "X"


def test_check_winner_diagonals():
    assert game_service._check_winner("X   X   X") == "X"
    assert game_service._check_winner("  X X X  ") == "X"


def test_check_winner_draw():
    # Полное поле без победителя
    assert game_service._check_winner("XOXOXOOXO") == "draw"


def test_check_winner_in_progress():
    assert game_service._check_winner("         ") is None
    assert game_service._check_winner("X        ") is None


def test_number_color():
    assert game_service._number_color(0) == "green"
    assert game_service._number_color(1) == "red"
    assert game_service._number_color(2) == "black"
    assert game_service._number_color(36) == "red"


def _room(state=None, bet=0):
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        game_type=GameType.TTT,
        chat_id=1,
        initiator_id=10,
        target_id=20,
        status=GameRoomStatus.ACTIVE,
        state=state or {"board": " " * 9, "turn": "X"},
        bet=bet,
        winner_id=None,
    )


async def test_ttt_action_initiator_move(monkeypatch):
    async def fake_update(room_id, **kwargs):
        return None

    monkeypatch.setattr(game_service.GameRoomOrm, "update", fake_update)
    room = _room()
    res = await game_service.ttt_action(room, 10, {"cell": 0})
    assert res["board"][0] == "X"
    assert res["turn"] == "O"
    assert res["winner"] is None


async def test_ttt_action_wrong_player(monkeypatch):
    async def fake_update(room_id, **kwargs):
        return None

    monkeypatch.setattr(game_service.GameRoomOrm, "update", fake_update)
    room = _room()
    # посторонний пользователь
    with pytest.raises(ValueError, match="не участник"):
        await game_service.ttt_action(room, 999, {"cell": 0})


async def test_ttt_action_not_your_turn(monkeypatch):
    async def fake_update(room_id, **kwargs):
        return None

    monkeypatch.setattr(game_service.GameRoomOrm, "update", fake_update)
    # ход O, но инициатор (X) пытается ходить
    room = _room(state={"board": "X        "[:9], "turn": "O"})
    with pytest.raises(ValueError, match="не ваш ход"):
        await game_service.ttt_action(room, 10, {"cell": 1})


async def test_ttt_action_occupied_cell(monkeypatch):
    async def fake_update(room_id, **kwargs):
        return None

    monkeypatch.setattr(game_service.GameRoomOrm, "update", fake_update)
    room = _room(state={"board": "X        "[:9], "turn": "X"})
    with pytest.raises(ValueError, match="занята"):
        await game_service.ttt_action(room, 10, {"cell": 0})


async def test_ttt_action_winning_move(monkeypatch):
    async def fake_update(room_id, **kwargs):
        return None

    monkeypatch.setattr(game_service.GameRoomOrm, "update", fake_update)
    # XX_ на верхней линии — ход в клетку 2 даёт победу инициатору
    room = _room(state={"board": "XX       "[:9], "turn": "X"})
    res = await game_service.ttt_action(room, 10, {"cell": 2})
    assert res["board"] == "XXX      "
    assert res["winner"] == 10  # initiator_id
