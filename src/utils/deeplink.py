
import re
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
    "minigame_blackjack": "mb",
    "casino": "c",
    "subscribe": "sub",
    "donate": "don",
    "advertise": "ad",
    "profile": "p",
}
"""Короткие Telegram start-link payload (лимит 64 символа на итоговый payload).

Формат plaintext (только [A-Za-z0-9_-]), далее encode=True (base64url):
  {func}[_{chat}][_r{short8}]
где chat = n{absChatId} для отрицательных / {chatId} для положительных.
Примеры: mr_n1001234567890_rabcdef12, mt_n1001234567890_r1a2b3c4d, sub
"""

SHORT_TO_FUNC = {v: k for k, v in FUNC_TO_SHORT.items()}

# mr_n100123..._rabcdef12  или  sub  или  c_12345
_PAYLOAD_RE = re.compile(
    r"^([A-Za-z]+)(?:_(n?-?\d+))?(?:_r([A-Za-z0-9]+))?$"
)


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


def _encode_chat_id(chat_id: int) -> str:
    cid = int(chat_id)
    if cid < 0:
        return f"n{abs(cid)}"
    return str(cid)


def _decode_chat_id(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip()
    if t.startswith("n") and t[1:].isdigit():
        return str(-int(t[1:]))
    if t.lstrip("-").isdigit():
        return t
    return None


def build_payload(*, request_func: str, chat_id: int | None = None, room_id: str | None = None) -> str:
    """Alphanumeric-only plaintext (для encode=True). Без & = и прочих символов."""
    short_f = FUNC_TO_SHORT.get(request_func, request_func)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", short_f or ""):
        raise ValueError(f"bad request_func short: {short_f!r}")
    parts = [short_f]
    if chat_id is not None:
        parts.append(_encode_chat_id(int(chat_id)))
    if room_id:
        parts.append(f"r{remember_room_short(str(room_id))}")
    payload = "_".join(parts)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", payload):
        raise ValueError(f"payload has illegal chars: {payload!r}")
    # encode=True ≈ +33%; Telegram лимит 64 на итоговый start-параметр
    if len(payload) > 48:
        raise ValueError(f"start payload too long for encode ({len(payload)}): {payload}")
    return payload


async def create_dm_start_link(
    bot: Bot,
    *,
    request_func: str,
    chat_id: int | None = None,
    room_id: str | None = None,
) -> str:
    """t.me start-link: alphanumeric payload + encode=True (aiogram base64url)."""
    payload = build_payload(request_func=request_func, chat_id=chat_id, room_id=room_id)
    link = await create_start_link(bot, payload, encode=True)
    # финальный payload после ?start= должен быть ≤64
    if "start=" in link:
        enc = link.rsplit("start=", 1)[-1]
        if len(enc) > 64:
            raise ValueError(f"encoded start payload too long ({len(enc)}): {enc}")
    return link


def parse_start_args(args: str) -> dict:
    """Новый alphanumeric (mr_n..._r...), старый query (f=/request_func=), и plain."""
    raw = (args or "").strip()
    if not raw:
        return {"request_func": None, "chat_id": None, "room": None}

    # 1) Новый короткий формат: mt_n100..._rabcdef12
    m = _PAYLOAD_RE.match(raw)
    if m and ("=" not in raw) and ("&" not in raw):
        short_f, chat_tok, room_tok = m.group(1), m.group(2), m.group(3)
        # room part may be glued as _rXXX → group3; or last part started with r
        return {
            "request_func": SHORT_TO_FUNC.get(short_f, short_f),
            "chat_id": _decode_chat_id(chat_tok),
            "room": room_tok,
        }

    # 2) query-string (старый f=mr&c=... или request_func=...)
    params = parse_qs(raw)

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
