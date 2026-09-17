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
    refreshed = await GameRoomOrm.get(str(room.id))
    return {
        "board": board,
        "turn": state.get("turn"),
        "winner": state.get("winner"),
        "status": _room_status(refreshed or room),
    }


# ---------------- Рулетка (до 8 игроков) ----------------

ROULETTE_NUMBERS = list(range(37))  # 0..36
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def _number_color(n: int) -> str:
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


def _roulette_bet_wins(btype: str, bval, number: int, color: str) -> int | None:
    """Множитель выплаты (включая возврат ставки) или None если проигрыш.
    European: number x36, color/parity/highlow x2, dozen/column x3.
    """
    if number == 0:
        # zero: only straight-up 0 wins (and green color)
        if btype == "number" and int(bval) == 0:
            return 36
        if btype == "color" and bval == "green":
            return 2
        return None

    if btype == "number":
        return 36 if int(bval) == number else None
    if btype == "color":
        return 2 if bval == color else None
    if btype == "parity":
        is_even = number % 2 == 0
        if bval == "even" and is_even:
            return 2
        if bval == "odd" and not is_even:
            return 2
        return None
    if btype == "highlow":
        if bval in ("low", "1-18") and 1 <= number <= 18:
            return 2
        if bval in ("high", "19-36") and 19 <= number <= 36:
            return 2
        return None
    if btype == "dozen":
        # 1 / 2 / 3  or "1st"/"2nd"/"3rd"
        mapping = {"1": 1, "2": 2, "3": 3, "1st": 1, "2nd": 2, "3rd": 3, 1: 1, 2: 2, 3: 3}
        d = mapping.get(bval)
        if d == 1 and 1 <= number <= 12:
            return 3
        if d == 2 and 13 <= number <= 24:
            return 3
        if d == 3 and 25 <= number <= 36:
            return 3
        return None
    if btype == "column":
        # columns: 1 -> 1,4,7...; 2 -> 2,5,8...; 3 -> 3,6,9...
        mapping = {"1": 1, "2": 2, "3": 3, 1: 1, 2: 2, 3: 3}
        c = mapping.get(bval)
        if c and number > 0 and ((number - 1) % 3) + 1 == c:
            return 3
        return None
    return None


async def roulette_join(room: GameRoomOrm, user_id: int, bet: int) -> dict:
    """Зарегистрировать игрока за столом (без обязательного списания — ставки списываются при place/spin)."""
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Комната недоступна")

    state = dict(room.state or {})
    players: list[dict] = list(state.get("players", []))

    if not any(p.get("user_id") == user_id for p in players):
        if len(players) >= _settings.GAME_ROULETTE_MAX_PLAYERS:
            raise ValueError("Достигнут максимум игроков")
        players.append({"user_id": user_id, "bet": 0})

    # Опциональный депозит фишек на стол (совместимость со старым клиентом)
    charged = 0
    if bet > 0:
        ok = await _charge_bet(room.chat_id, user_id, bet)
        if not ok:
            raise ValueError("Недостаточно васякоинов для ставки")
        charged = bet
        for p in players:
            if p.get("user_id") == user_id:
                p["bet"] = int(p.get("bet", 0)) + bet
                break

    state["players"] = players
    new_status = GameRoomStatus.ACTIVE if room.status == GameRoomStatus.WAITING else room.status
    await GameRoomOrm.update(str(room.id), state=state, status=new_status)
    return {"joined": True, "players_count": len(players), "bet": charged, "status": new_status.value}


async def roulette_place_bets(room: GameRoomOrm, user_id: int, bets: list[dict]) -> dict:
    """Поставить фишки: списать баланс и сохранить ставки в state.pending_bets."""
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Комната недоступна")
    if room.status == GameRoomStatus.FINISHED:
        raise ValueError("Раунд завершён — создайте новую игру")

    state = dict(room.state or {})
    players: list[dict] = list(state.get("players", []))
    if not any(p.get("user_id") == user_id for p in players):
        if len(players) >= _settings.GAME_ROULETTE_MAX_PLAYERS:
            raise ValueError("Достигнут максимум игроков")
        players.append({"user_id": user_id, "bet": 0})

    pending: list[dict] = list(state.get("pending_bets", []))
    # Уберём предыдущие неразыгранные ставки этого игрока и вернём деньги? —
    # проще: добавляем к pending, списывая каждую новую.
    normalized: list[dict] = []
    total = 0
    for raw in bets or []:
        amount = int(raw.get("amount", 0))
        if amount <= 0:
            continue
        btype = str(raw.get("type", ""))
        bval = raw.get("value")
        if btype not in ("number", "color", "parity", "highlow", "dozen", "column"):
            raise ValueError(f"Неизвестный тип ставки: {btype}")
        total += amount
        normalized.append({
            "user_id": user_id,
            "type": btype,
            "value": bval,
            "amount": amount,
        })

    if total <= 0:
        raise ValueError("Добавьте хотя бы одну ставку")

    ok = await _charge_bet(room.chat_id, user_id, total)
    if not ok:
        raise ValueError("Недостаточно васякоинов для ставки")

    pending.extend(normalized)
    for p in players:
        if p.get("user_id") == user_id:
            p["bet"] = int(p.get("bet", 0)) + total
            break

    state["players"] = players
    state["pending_bets"] = pending
    await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
    return {
        "ok": True,
        "charged": total,
        "pending_bets": [b for b in pending if b.get("user_id") == user_id],
        "pending_total": sum(int(b.get("amount", 0)) for b in pending if b.get("user_id") == user_id),
    }


async def roulette_spin(room: GameRoomOrm, user_id: int, action: dict) -> dict:
    """Крутить рулетку.

    action:
      - bets: optional list — если переданы, сначала place (списание), затем спин
      - иначе берутся state.pending_bets

    После спина стол остаётся ACTIVE (новый раунд), pending очищается.
    Крутить может любой участник стола (не только initiator) — для соло-казино.
    """
    if room.status == GameRoomStatus.FINISHED:
        raise ValueError("Стол закрыт — создайте новую игру")
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Рулетка недоступна")

    state = dict(room.state or {})
    players: list[dict] = list(state.get("players", []))

    # Авто-join крутящего (persist), чтобы place/spin видели участника
    if not any(p.get("user_id") == user_id for p in players):
        if len(players) >= _settings.GAME_ROULETTE_MAX_PLAYERS:
            raise ValueError("Достигнут максимум игроков")
        players.append({"user_id": user_id, "bet": 0})
        state["players"] = players
        await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
        room = await GameRoomOrm.get(str(room.id))
        state = dict(room.state or {})

    incoming = action.get("bets")
    if incoming:
        await roulette_place_bets(room, user_id, incoming)
        room = await GameRoomOrm.get(str(room.id))
        state = dict(room.state or {})

    bets: list[dict] = list(state.get("pending_bets") or [])
    if not bets:
        raise ValueError("Нет ставок на столе — сделайте ставку")

    number = random.choice(ROULETTE_NUMBERS)
    color = _number_color(number)

    payouts: list[dict] = []
    # агрегируем по user_id
    by_user: dict[int, dict] = {}
    for bet in bets:
        uid = int(bet.get("user_id") or user_id)
        amount = int(bet.get("amount", 0))
        mult = _roulette_bet_wins(str(bet.get("type")), bet.get("value"), number, color)
        won = amount * mult if mult else 0
        slot = by_user.setdefault(uid, {"user_id": uid, "bet": 0, "won": 0})
        slot["bet"] += amount
        slot["won"] += won
        payouts.append({
            "user_id": uid,
            "type": bet.get("type"),
            "value": bet.get("value"),
            "bet": amount,
            "won": won,
            "won_net": won - amount,
        })

    results = []
    for uid, agg in by_user.items():
        won = int(agg["won"])
        bet_sum = int(agg["bet"])
        if won > 0:
            await _payout(room.chat_id, uid, won)
        results.append({
            "user_id": uid,
            "bet": bet_sum,
            "won": won,
            "won_net": won - bet_sum,
        })

    history = list(state.get("history", []))
    history.append({"number": number, "color": color, "results": results})
    state["history"] = history[-30:]
    state["last_number"] = number
    state["last_color"] = color
    state["pending_bets"] = []
    # сброс «банка» игроков на столе после раунда
    for p in state.get("players", []):
        p["bet"] = 0

    await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
    return {
        "number": number,
        "color": color,
        "results": results,
        "bets": payouts,
        "status": "active",
    }


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


    if room.game_type == GameType.TTT:
        await _notify_ttt_finished(room, winner_id, draw)


async def _notify_ttt_finished(room: GameRoomOrm, winner_id: int | None, draw: bool) -> None:
    """Сообщение в исходный групповой чат: кто выиграл / кто проиграл."""
    try:
        from shared.models.user import UserOrm
        from shared.messaging import ensure_bus

        async def _name(uid: int | None) -> str:
            if not uid:
                return "игрок"
            u = await UserOrm.get_user_by_id(uid)
            if u and getattr(u, "first_name", None):
                return (u.first_name or "игрок").strip()
            return f"id {uid}"

        a = await _name(room.initiator_id)
        b = await _name(room.target_id)
        if draw:
            text = f"⚔️ Дуэль крестики-нолики: ничья.\n{a} vs {b}"
        elif winner_id == room.initiator_id:
            text = f"⚔️ Дуэль крестики-нолики окончена.\nПобедил {a}, проиграл {b}."
        elif winner_id == room.target_id:
            text = f"⚔️ Дуэль крестики-нолики окончена.\nПобедил {b}, проиграл {a}."
        else:
            text = f"⚔️ Дуэль крестики-нолики окончена.\n{a} vs {b}"

        bus = await ensure_bus()
        await bus.publish(
            "api.game.finished",
            {"chat_id": int(room.chat_id), "result_text": text},
        )
    except Exception:
        logger.exception("не удалось уведомить чат о результате TTT room=%s", room.id)



# ---------------- Блэкджек (соло vs дилер) ----------------

_BJ_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_BJ_SUITS = ["♠", "♥", "♦", "♣"]


def _bj_new_deck() -> list[str]:
    deck = [f"{r}{s}" for s in _BJ_SUITS for r in _BJ_RANKS]
    random.shuffle(deck)
    return deck


def _bj_card_value(card: str) -> int:
    rank = card[:-1]
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def _bj_hand_value(cards: list[str]) -> int:
    total = sum(_bj_card_value(c) for c in cards)
    aces = sum(1 for c in cards if c.startswith("A"))
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _bj_public_state(state: dict, reveal_dealer: bool = False) -> dict:
    dealer = list(state.get("dealer") or [])
    if not reveal_dealer and dealer:
        dealer_view = [dealer[0], "??"] + dealer[2:]
    else:
        dealer_view = dealer
    return {
        "phase": state.get("phase", "bet"),
        "player": list(state.get("player") or []),
        "dealer": dealer_view,
        "player_value": _bj_hand_value(state.get("player") or []),
        "dealer_value": _bj_hand_value(dealer) if reveal_dealer else (
            _bj_card_value(dealer[0]) if dealer else 0
        ),
        "bet": int(state.get("bet") or 0),
        "result": state.get("result"),
        "payout": int(state.get("payout") or 0),
        "message": state.get("message"),
        "net": int(state["payout"] - state["bet"]) if state.get("phase") == "finished" else None,
    }


async def blackjack_action(room: GameRoomOrm, user_id: int, action: dict) -> dict:
    """Соло-блэкджек. action: {op: deal|hit|stand, bet?: int}"""
    if room.status not in (GameRoomStatus.WAITING, GameRoomStatus.ACTIVE):
        raise ValueError("Блэкджек недоступен")

    op = str(action.get("op") or action.get("action") or "").lower()
    state = dict(room.state or {})
    phase = state.get("phase", "bet")

    if op == "deal":
        if phase not in ("bet", "finished", None, ""):
            raise ValueError("Сначала завершите текущую раздачу")
        bet = int(action.get("bet") or 0)
        if bet <= 0:
            raise ValueError("Ставка должна быть положительной")
        ok = await _charge_bet(room.chat_id, user_id, bet)
        if not ok:
            raise ValueError("Недостаточно васякоинов")

        deck = _bj_new_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        state = {
            "phase": "player",
            "deck": deck,
            "player": player,
            "dealer": dealer,
            "bet": bet,
            "result": None,
            "payout": 0,
            "message": None,
        }
        # Natural blackjack?
        pv = _bj_hand_value(player)
        dv = _bj_hand_value(dealer)
        if pv == 21 or dv == 21:
            state = await _bj_settle(room, user_id, state, natural=True)
        await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
        reveal = state.get("phase") == "finished"
        return _bj_public_state(state, reveal_dealer=reveal)

    if op == "hit":
        if phase != "player":
            raise ValueError("Сейчас нельзя взять карту")
        deck = list(state.get("deck") or [])
        if not deck:
            deck = _bj_new_deck()
        state.setdefault("player", []).append(deck.pop())
        state["deck"] = deck
        if _bj_hand_value(state["player"]) > 21:
            state = await _bj_settle(room, user_id, state)
        await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
        reveal = state.get("phase") == "finished"
        return _bj_public_state(state, reveal_dealer=reveal)

    if op == "stand":
        if phase != "player":
            raise ValueError("Сейчас нельзя остановиться")
        # Дилер добирает до 17+
        deck = list(state.get("deck") or [])
        dealer = list(state.get("dealer") or [])
        while _bj_hand_value(dealer) < 17:
            if not deck:
                deck = _bj_new_deck()
            dealer.append(deck.pop())
        state["dealer"] = dealer
        state["deck"] = deck
        state = await _bj_settle(room, user_id, state)
        await GameRoomOrm.update(str(room.id), state=state, status=GameRoomStatus.ACTIVE)
        return _bj_public_state(state, reveal_dealer=True)

    raise ValueError("Неизвестное действие блэкджека (deal|hit|stand)")


async def _bj_settle(room: GameRoomOrm, user_id: int, state: dict, natural: bool = False) -> dict:
    player = list(state.get("player") or [])
    dealer = list(state.get("dealer") or [])
    bet = int(state.get("bet") or 0)
    pv = _bj_hand_value(player)
    dv = _bj_hand_value(dealer)
    payout = 0
    result = "lose"
    message = ""

    if pv > 21:
        result, message = "lose", "Перебор! Вы проиграли"
    elif natural and pv == 21 and dv != 21:
        payout = bet + int(bet * 3 / 2)  # ставка + 3:2
        result, message = "blackjack", "Блэкджек! Выигрыш 3:2"
    elif natural and pv == 21 and dv == 21:
        payout = bet
        result, message = "push", "Два блэкджека — ничья, ставка возвращена"
    elif dv > 21:
        payout = bet * 2
        result, message = "win", "Дилер перебрал — вы выиграли"
    elif pv > dv:
        payout = bet * 2
        result, message = "win", "Вы выиграли"
    elif pv == dv:
        payout = bet
        result, message = "push", "Ничья — ставка возвращена"
    else:
        result, message = "lose", "Дилер выиграл"

    if payout > 0:
        await _payout(room.chat_id, user_id, payout)

    state.update(
        {
            "phase": "finished",
            "result": result,
            "payout": payout,
            "message": message,
            "net": payout - bet,
        }
    )
    return state


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
