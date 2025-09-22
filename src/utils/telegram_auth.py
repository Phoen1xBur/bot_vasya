import hmac
import hashlib
import logging
from urllib.parse import parse_qs
import json


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    logger = logging.getLogger(__name__)
    try:
        parsed_data = parse_qs(init_data)
        hash_value = parsed_data.pop('hash', [''])[0]

        data_check_string = '\n'.join(
            f"{k}={v[0]}" for k, v in sorted(parsed_data.items())
        )

        secret_key = hashlib.sha256(bot_token.encode()).digest()
        hmac_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        valid = hmac.compare_digest(hmac_hash, hash_value)
        if not valid:
            logger.debug("Некорректные Telegram init data: data=%s", data_check_string)
        return valid
    except Exception as e:
        logger.exception("Ошибка при проверке Telegram init data: %s", e)
        return False


def get_user_id_from_init_data(init_data: str) -> int:
    logger = logging.getLogger(__name__)
    try:
        parsed_data = parse_qs(init_data)
        user_data = parsed_data.get('user', ['{}'])[0]
        user_dict = json.loads(user_data)
        return user_dict.get('id')
    except Exception as e:
        logger.exception("Ошибка при разборе user id из init data: %s", e)
        return 0


def get_user_profile_from_init_data(init_data: str) -> dict:
    """Возвращает {id, username, first_name, last_name} из init data"""
    logger = logging.getLogger(__name__)
    try:
        parsed_data = parse_qs(init_data)
        user_data = parsed_data.get('user', ['{}'])[0]
        user_dict = json.loads(user_data)
        return {
            'id': user_dict.get('id'),
            'username': user_dict.get('username'),
            'first_name': user_dict.get('first_name'),
            'last_name': user_dict.get('last_name'),
        }
    except Exception as e:
        logger.exception("Ошибка при разборе профиля из init data: %s", e)
        return {}
