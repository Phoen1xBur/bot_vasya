"""Проверка подписи Telegram WebApp initData (HMAC-SHA256).

По документации Telegram Mini Apps:
  secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  hash       = HMAC_SHA256(key=secret_key, msg=data_check_string)
"""

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)


def _parse_init_data(init_data: str) -> dict[str, str]:
    """parse_qsl сохраняет значения как есть (без list-обёртки parse_qs)."""
    return dict(parse_qsl(init_data, keep_blank_values=True))


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    try:
        parsed = _parse_init_data(init_data)
        hash_value = parsed.pop("hash", "")
        if not hash_value or not bot_token:
            return False

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        # Правильный секрет для Mini Apps / WebApp initData:
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        hmac_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        valid = hmac.compare_digest(hmac_hash, hash_value)
        if not valid:
            logger.debug("Некорректные Telegram init data: %s", data_check_string)
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
