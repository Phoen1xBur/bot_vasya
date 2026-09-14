"""Проверка подписи Telegram WebApp initData (HMAC-SHA256)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    try:
        parsed_data = parse_qs(init_data)
        hash_value = parsed_data.pop("hash", [""])[0]

        data_check_string = "\n".join(
            f"{k}={v[0]}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hashlib.sha256(bot_token.encode()).digest()
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
        parsed_data = parse_qs(init_data)
        user_data = parsed_data.get("user", ["{}"])[0]
        return json.loads(user_data).get("id") or 0
    except Exception:
        logger.exception("Ошибка разбора user id из init data")
        return 0


def get_user_profile_from_init_data(init_data: str) -> dict:
    try:
        parsed_data = parse_qs(init_data)
        user_data = parsed_data.get("user", ["{}"])[0]
        d = json.loads(user_data)
        return {
            "id": d.get("id"),
            "username": d.get("username"),
            "first_name": d.get("first_name"),
            "last_name": d.get("last_name"),
        }
    except Exception:
        logger.exception("Ошибка разбора профиля из init data")
        return {}
