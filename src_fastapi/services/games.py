"""Логика мини-игр: TTT (дуэль 1×1), Рулетка (до 8 игроков), Слот-машина.

Ставки — в васякоинах чата-источника (chat_id комнаты).
Комиссия бота — GAME_COMMISSION_PERCENT со ставок.
"""

import logging
import random
from typing import Any

from shared.config import get_settings
from shared.enums import GameRoomStatus, GameType
from shared.models.game_room import GameRoomOrm
from shared.models.group_user import GroupUserOrm
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
_settings = get_settings()


# ---------------- TTT (крестики-нолики, дуэль 1×1) ----------------

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def _check_winner(board: str) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board:
        return "draw"
    return None


async def ttt_action(room: GameRoomOrm, user_id: int, action: dict) -> dict:
    """Ход в крестики-нолики. action: {"cell": 0..8}"""
    state = room.state or {}
    board = state.get("board", " " * 9)
    turn = state.get("turn", "X")

    if room.status != GameRoomStatus.ACTIVE:
        raise ValueError("Игра не активна")

    # X = initiator, O = target
    if user_id == room.initiator_id:
        mark = "X"
    elif user_id == room.target_id:
        mark = "O"
    else:
        raise ValueError("Вы не участник этой дуэли")

    if mark != turn:
        raise ValueError("Сейчас не ваш ход")

    cell = int(action.get("cell", -1))
    if cell < 0 or cell > 8:
        raise ValueError("Неверная клетка")
    if board[cell] != " ":
        raise ValueError("Клетка занята")

    board = board[:cell] + mark + board[cell + 1 :]
    state["board"] = board
    winner = _check_winner(board)

    if winner == "X":
        state["winner"] = room.initiator_id
        await _finish_game(room, winner_id=room.initiator_id)
    elif winner == "O":
        state["winner"] = room.target_id
        await _finish_game(room, winner_id=room.target_id)
    elif winner == "draw":
        state["winner"] = 0
        await _finish_game(room, winner_id=0, draw=True)
    else:
        state["turn"] = "O" if turn == "X" else "X"

    await GameRoomOrm.update(str(room.id), state=state)
    return {"board": board, "turn": state.get("turn"), "winner": state.get("winner"), "status": _room_status(room)}


# ---------------- Рулетка (до 8 игроков) ----------------

ROULETTE_NUMBERS = list(range(37))  # 0..36
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def _number_color(n: int) -> str:
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


async def roulette_join(room: GameRoomOrm, user_id: int, bet: int) -> dict:
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Комната недоступна")

    state = room.state or {}
    players: list[dict] = state.get("players", [])

    if len(players) >= _settings.GAME_ROULETTE_MAX_PLAYERS:
        raise ValueError("Достигнут максимум игроков")

    # Проверка баланса
    ok = await _charge_bet(room.chat_id, user_id, bet)
    if not ok:
        raise ValueError("Недостаточно васякоинов для ставки")

    # Если игрок уже в игре — обновляем ставку
    found = False
    for p in players:
        if p["user_id"] == user_id:
            p["bet"] += bet
            found = True
            break
    if not found:
        players.append({"user_id": user_id, "bet": bet})

    state["players"] = players
    if room.status == GameRoomStatus.WAITING:
        await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
    else:
        await GameRoomOrm.update(str(room.id), state=state)
    return {"joined": True, "players_count": len(players), "bet": bet}


async def roulette_spin(room: GameRoomOrm, user_id: int, action: dict) -> dict:
    """Крутить рулетку. action: {"bets": [{"user_id","type","value","amount"}]}

    Упрощённая модель: каждый игрок ставит на цвет/число/чёт-нечет.
    """
    if room.status != GameRoomStatus.ACTIVE:
        raise ValueError("Рулетка не активна")
    # Крутить может инициатор
    if user_id != room.initiator_id:
        raise ValueError("Крутить может только создатель стола")

    state = room.state or {}
    incoming = action.get("bets", [])
    # Нормализуем ставки и пишем в state (видно другим игрокам)
    normalized = []
    for bet in incoming:
        normalized.append({
            "user_id": bet.get("user_id") or user_id,
            "type": bet.get("type"),
            "value": bet.get("value"),
            "amount": int(bet.get("amount", 0)),
        })
    if normalized:
        state["bets"] = (state.get("bets") or []) + normalized
        await GameRoomOrm.update(str(room.id), state=state)
    bets: list[dict] = state.get("bets") or normalized
    number = random.choice(ROULETTE_NUMBERS)
    color = _number_color(number)

    # Выплаты
    payouts: list[dict] = []
    for bet in bets:
        uid = bet.get("user_id") or user_id
        btype = bet.get("type")
        bval = bet.get("value")
        amount = int(bet.get("amount", 0))
        won = 0
        if btype == "number" and int(bval) == number:
            won = amount * 36
        elif btype == "color" and bval == color:
            won = amount * 2
        elif btype == "parity":
            is_even = number % 2 == 0
            if (bval == "even" and is_even) or (bval == "odd" and not is_even):
                won = amount * 2
        payouts.append({"user_id": uid, "bet": amount, "won": won, "won_net": won - amount})

    # Выплата выигрышей
    for p in payouts:
        if p["won"] > 0:
            await _payout(room.chat_id, p["user_id"], p["won"])

    await _finish_game(room, winner_id=0)
    return {"number": number, "color": color, "results": payouts}


# ---------------- Слот-машина ----------------

# Символы и выплаты (множитель ставки)
SLOT_SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
SLOT_PAYOUTS = {
    "💎": 10,
    "7️⃣": 25,
    "⭐": 5,
    "🔔": 4,
    "🍋": 3,
    "🍒": 2,
}


async def slots_spin(room: GameRoomOrm, user_id: int, action: dict) -> dict:
    """Крутить слот-машину. action: {"bet": int}"""
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Слот недоступен")

    bet = int(action.get("bet", room.bet or 0))
    if bet <= 0:
        raise ValueError("Ставка должна быть положительной")

    ok = await _charge_bet(room.chat_id, user_id, bet)
    if not ok:
        raise ValueError("Недостаточно васякоинов")

    # 3 барабана
    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    won = 0
    if reels[0] == reels[1] == reels[2]:
        # 3 одинаковых
        won = bet * SLOT_PAYOUTS.get(reels[0], 2)
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # 2 одинаковых — малый выигрыш
        won = int(bet * 0.5)

    if won > 0:
        await _payout(room.chat_id, user_id, won)

    state = room.state or {}
    history: list = state.get("history", [])
    history.append({"reels": reels, "bet": bet, "won": won})
    state["history"] = history[-20:]  # последние 20
    state["last_reels"] = reels
    state["last_won"] = won
    await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)

    return {"reels": reels, "won": won, "bet": bet, "net": won - bet}


# ---------------- Вспомогательные ----------------


async def _charge_bet(chat_id: int, user_id: int, amount: int) -> bool:
    """Списать ставку с баланса пользователя в чате. Возвращает False если не хватает."""
    try:
        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user is None or group_user.money < amount:
            return False
        await group_user.money_minus(amount)
        return True
    except Exception:
        logger.exception("Ошибка списания ставки chat=%s user=%s", chat_id, user_id)
        return False


async def _payout(chat_id: int, user_id: int, amount: int) -> None:
    """Выплата выигрыша на баланс в чате (минус комиссия)."""
    try:
        commission = int(amount * _settings.GAME_COMMISSION_PERCENT / 100)
        payout = amount - commission
        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user is None:
            # создаём, если нет
            from shared.models.user import UserOrm

            await UserOrm.insert_or_update_user(user_id)
            from shared.models.chat import TelegramChatOrm

            await TelegramChatOrm.insert_or_update_telegram_chat(chat_id)
            group_user = await GroupUserOrm.insert_or_update_group_user(
                user_id, chat_id, money=0
            )
        await group_user.money_plus(payout)
    except Exception:
        logger.exception("Ошибка выплаты chat=%s user=%s", chat_id, user_id)


def _room_status(room: GameRoomOrm) -> str:
    return room.status.value if hasattr(room.status, "value") else str(room.status)


async def _finish_game(room: GameRoomOrm, winner_id: int | None, draw: bool = False) -> None:
    """Завершить игру: для ставок распределяем банк."""
    await GameRoomOrm.update(
        str(room.id),
        status=GameRoomStatus.FINISHED,
        winner_id=winner_id,
    )
    # Для дуэли (TTT) со ставкой — победитель забирает банк (минус комиссия)
    if room.game_type == GameType.TTT and room.bet > 0 and winner_id and not draw:
        bank = room.bet * 2
        await _payout(room.chat_id, winner_id, bank)


async def get_room_state_view(room: GameRoomOrm) -> dict:
    return {
        "id": str(room.id),
        "game_type": room.game_type.value if hasattr(room.game_type, "value") else str(room.game_type),
        "chat_id": room.chat_id,
        "initiator_id": room.initiator_id,
        "target_id": room.target_id,
        "status": _room_status(room),
        "state": room.state,
        "bet": room.bet,
        "winner_id": room.winner_id,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "expires_at": room.expires_at.isoformat() if room.expires_at else None,
    }
