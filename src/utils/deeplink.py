"""Короткие Telegram start-link payload (лимит 64 символа)."""

from __future__ import annotations

from urllib.parse import parse_qs

from aiogram import Bot
from aiogram.utils.deep_linking import create_start_link

from shared.config import get_settings
from shared.redis_client import get_redis

_settings = get_settings()

FUNC_TO_SHORT = {
    "minigame_roulette": "mr",
    "minigame_slots": "ms",
    "minigame_ttt": "mt",
    "casino": "c",
    "subscribe": "sub",
    "donate": "don",
    "advertise": "ad",
    "profile": "p",
}
SHORT_TO_FUNC = {v: k for k, v in FUNC_TO_SHORT.items()}


def room_short_code(room_id: str) -> str:
    return str(room_id).replace("-", "")[:8]


def remember_room_short(room_id: str, ttl_seconds: int | None = None) -> str:
    short = room_short_code(room_id)
    ttl = ttl_seconds or int(_settings.GAME_ROOM_TTL_MINUTES) * 60
    try:
        r = get_redis()
        r.setex(f"game:room:short:{short}", ttl, str(room_id))
        r.setex(f"game:room:{room_id}", ttl, str(room_id))
    except Exception:
        pass
    return short


async def resolve_room_id(short_or_full: str | None) -> str | None:
    if not short_or_full:
        return None
    raw = str(short_or_full).strip()
    if len(raw) >= 32 and "-" in raw:
        return raw
    short = raw.replace("-", "")[:8]
    try:
        val = get_redis().get(f"game:room:short:{short}")
        if val is not None:
            return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)
    except Exception:
        pass
    try:
        from shared.database import async_session_factory
        from sqlalchemy import text

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id::text FROM game_room "
                    "WHERE replace(id::text, '-', '') LIKE :pfx "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"pfx": f"{short}%"},
            )
            row = result.first()
            if row:
                return str(row[0])
    except Exception:
        pass
    return raw if len(raw) > 8 else None


def build_payload(*, request_func: str, chat_id: int | None = None, room_id: str | None = None) -> str:
    short_f = FUNC_TO_SHORT.get(request_func, request_func)
    parts = [f"f={short_f}"]
    if chat_id is not None:
        parts.append(f"c={int(chat_id)}")
    if room_id:
        parts.append(f"r={remember_room_short(str(room_id))}")
    payload = "&".join(parts)
    if len(payload) > 64:
        raise ValueError(f"start payload too long ({len(payload)}): {payload}")
    return payload


async def create_dm_start_link(
    bot: Bot,
    *,
    request_func: str,
    chat_id: int | None = None,
    room_id: str | None = None,
) -> str:
    """t.me start-link с коротким payload без base64 (лимит Telegram — 64)."""
    payload = build_payload(request_func=request_func, chat_id=chat_id, room_id=room_id)
    return await create_start_link(bot, payload, encode=False)


def parse_start_args(args: str) -> dict:
    """Короткий (f/c/r) и старый (request_func/chat_id/room) формат."""
    params = parse_qs(args or "")

    def one(key: str):
        vals = params.get(key)
        return vals[0] if vals else None

    f = one("f")
    c = one("c")
    r = one("r")
    if f or c or r:
        return {
            "request_func": SHORT_TO_FUNC.get(f or "", f),
            "chat_id": c,
            "room": r,
        }

    return {
        "request_func": one("request_func"),
        "chat_id": one("chat_id"),
        "room": one("room"),
    }
