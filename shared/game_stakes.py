"""Refund of unplayed game stakes (cancel / expire). Shared by API + bot."""

from __future__ import annotations

import logging

from shared.enums import GameRoomStatus, GameType
from shared.models.group_user import GroupUserOrm

logger = logging.getLogger(__name__)


async def refund_bet(chat_id: int, user_id: int, amount: int) -> None:
    """Return a previously charged stake. amount must be > 0."""
    amount = int(amount)
    if amount <= 0:
        return
    try:
        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user is None:
            return
        await group_user.money_plus(amount)
    except Exception:
        logger.exception("Ошибка возврата ставки chat=%s user=%s", chat_id, user_id)


async def refund_room_stakes(room, status_override=None) -> None:
    """Вернуть списанные, но не разыгранные ставки при cancel/expire.

    - room.bet > 0: initiator (create); TTT ACTIVE → также target (join)
    - roulette pending_bets + orphan join-депозит (p.bet сверх pending)
    - blackjack mid-hand (phase=player): state.bet

    status_override: prior status when room already marked EXPIRED/CANCELLED.
    """
    status = status_override if status_override is not None else room.status
    if room.bet > 0:
        await refund_bet(room.chat_id, room.initiator_id, room.bet)
        if (
            room.game_type == GameType.TTT
            and status == GameRoomStatus.ACTIVE
            and room.target_id
        ):
            await refund_bet(room.chat_id, room.target_id, room.bet)

    if room.game_type == GameType.ROULETTE:
        state = dict(room.state or {})
        pending = list(state.get("pending_bets") or [])
        pending_by_uid: dict[int, int] = {}
        for b in pending:
            try:
                uid = int(b.get("user_id"))
                amt = int(b.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            if amt > 0:
                pending_by_uid[uid] = pending_by_uid.get(uid, 0) + amt
        for uid, amt in pending_by_uid.items():
            await refund_bet(room.chat_id, uid, amt)
        for p in state.get("players") or []:
            try:
                uid = int(p.get("user_id"))
                table = int(p.get("bet") or 0)
            except (TypeError, ValueError):
                continue
            orphan = table - pending_by_uid.get(uid, 0)
            if orphan > 0:
                await refund_bet(room.chat_id, uid, orphan)

    if room.game_type == GameType.BLACKJACK:
        state = dict(room.state or {})
        phase = state.get("phase")
        bet = int(state.get("bet") or 0)
        if bet > 0 and phase == "player":
            await refund_bet(room.chat_id, room.initiator_id, bet)
