import hmac
import hashlib
from urllib.parse import parse_qs
import json


def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
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

        return hmac.compare_digest(hmac_hash, hash_value)
    except:
        return False


def get_user_id_from_init_data(init_data: str) -> int:
    try:
        parsed_data = parse_qs(init_data)
        user_data = parsed_data.get('user', ['{}'])[0]
        user_dict = json.loads(user_data)
        return user_dict.get('id')
    except:
        return 0
