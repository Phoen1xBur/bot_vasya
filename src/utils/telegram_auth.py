import hmac
import hashlib
import logging
from typing import Any
from urllib.parse import parse_qsl
import json


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Проверяет корректность init_data, полученной от Telegram WebApp.
    Возвращает True, если данные подлинные, иначе False.
    """
    logger = logging.getLogger(__name__)
    try:
        # Преобразуем строку init_data в словарь (query string → dict)
        data_dict = dict(parse_qsl(init_data, strict_parsing=True))

        # Извлекаем hash из данных
        hash_received = data_dict.pop("hash", None)
        if not hash_received:
            return False

        # Сортируем оставшиеся поля по ключу (в алфавитном порядке)
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))

        # Создаем secret key из токена
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()

        # Считаем свой хэш
        hash_calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        valid = hmac.compare_digest(hash_calculated, hash_received)
        if not valid:
            logger.debug("Некорректные Telegram init data: data=%s", data_check_string)
        return valid
    except Exception as e:
        logger.exception("Ошибка при проверке Telegram init data: %s", e)
        return False


def get_user_id_from_init_data(init_data: str) -> int:
    logger = logging.getLogger(__name__)
    try:
        parsed_data = dict(parse_qsl(init_data))
        user_data = parsed_data.get('user', None)
        user_dict = json.loads(user_data)
        return user_dict.get('id')
    except Exception as e:
        logger.exception("Ошибка при разборе user id из init data: %s", e)
        return 0


def get_user_profile_from_init_data(init_data: str) -> str | None | dict[Any, Any]:
    """Возвращает {id, username, first_name, last_name} из init data"""
    logger = logging.getLogger(__name__)
    try:
        parsed_data = dict(parse_qsl(init_data))
        return parsed_data.get('user', None)
    except Exception as e:
        logger.exception("Ошибка при разборе профиля из init data: %s", e)
        return {}
