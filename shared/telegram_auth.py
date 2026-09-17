"""Проверка подписи Telegram WebApp initData (HMAC-SHA256).

По документации Telegram Mini Apps:
  secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)

Desktop-клиенты (tdesktop / web.telegram) иногда:
  - кладут initData в hash-фрагмент tgWebAppData
  - дополнительно URL-кодируют строку
  - добавляют поле signature (Ed25519) — для HMAC его НУЖНО оставлять в data_check_string
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl, unquote, unquote_plus

logger = logging.getLogger(__name__)


def normalize_init_data(init_data: str) -> str:
    """Приводит сырой initData к виду query-string для HMAC."""
    if not init_data:
        return ""
    s = init_data.strip()
    # Иногда прилетает целиком URL или hash-фрагмент
    if "#tgWebAppData=" in s:
        s = s.split("#tgWebAppData=", 1)[1]
    if s.startswith("tgWebAppData="):
        s = s[len("tgWebAppData=") :]
    if "?" in s and "hash=" in s and "user=" in s:
        # query часть URL
        s = s.split("?", 1)[-1]
    # Один уровень URL-decode, если строка ещё закодирована
    if "%3D" in s or "%26" in s or (s.count("%") > 2 and "hash=" not in s and "user=" not in s):
        s2 = unquote_plus(s)
        if "hash=" in s2 or "user=" in s2:
            s = s2
    elif "user=%7B" in s or "user=%7b" in s:
        # значения закодированы — parse_qsl сам декодирует; оставляем как есть
        pass
    return s


def _parse_init_data(init_data: str) -> dict[str, str]:
    """parse_qsl сохраняет значения как есть (без list-обёртки parse_qs)."""
    return dict(parse_qsl(normalize_init_data(init_data), keep_blank_values=True))


def _webapp_secret(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    try:
        parsed = _parse_init_data(init_data)
        hash_value = parsed.pop("hash", "")
        if not hash_value or not bot_token:
            return False

        # Для HMAC-валидации ботом поле signature НЕ исключается
        # (оно входит в data_check_string; исключается только hash).
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = _webapp_secret(bot_token)
        hmac_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        valid = hmac.compare_digest(hmac_hash, hash_value)
        if not valid:
            # Desktop иногда присылает уже decoded user JSON в другом порядке —
            # пробуем ещё раз с unquote всей строки (если ещё не декодировали)
            alt = unquote(normalize_init_data(init_data))
            if alt != normalize_init_data(init_data):
                parsed2 = dict(parse_qsl(alt, keep_blank_values=True))
                hv2 = parsed2.pop("hash", "")
                dcs2 = "\n".join(f"{k}={v}" for k, v in sorted(parsed2.items()))
                h2 = hmac.new(secret_key, dcs2.encode(), hashlib.sha256).hexdigest()
                valid = bool(hv2) and hmac.compare_digest(h2, hv2)
        if not valid:
            logger.debug(
                "Некорректные Telegram init data keys=%s",
                sorted(parsed.keys()),
            )
        return valid
    except Exception:
        logger.exception("Ошибка при проверке Telegram init data")
        return False


def get_user_id_from_init_data(init_data: str) -> int:
    try:
        parsed = _parse_init_data(init_data)
        user_data = parsed.get("user", "{}")
        return json.loads(user_data).get("id") or 0
    except Exception:
        logger.exception("Ошибка разбора user id из init data")
        return 0


def get_user_profile_from_init_data(init_data: str) -> dict:
    try:
        parsed = _parse_init_data(init_data)
        if "user" not in parsed:
            return {}
        d = json.loads(parsed.get("user", "{}"))
        if not isinstance(d, dict) or d.get("id") is None:
            return {}
        return {
            "id": d.get("id"),
            "username": d.get("username"),
            "first_name": d.get("first_name"),
            "last_name": d.get("last_name"),
        }
    except Exception:
        logger.exception("Ошибка разбора профиля из init data")
        return {}
