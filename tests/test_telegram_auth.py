"""Тесты проверки подписи Telegram WebApp initData (HMAC-SHA256)."""
import hashlib
import hmac
import json
from urllib.parse import urlencode, quote

from shared.telegram_auth import (
    get_user_profile_from_init_data,
    validate_telegram_init_data,
)

BOT_TOKEN = "123:test:token"


def _sign(params: dict) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    params = dict(params)
    params["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(params)


def _make_init_data(user_id: int = 42, username: str = "alice", first: str = "Alice", extra: dict | None = None) -> str:
    """Собирает валидный initData с корректной WebAppData HMAC-подписью."""
    params = {
        "query_id": "query_123",
        "user": json.dumps(
            {"id": user_id, "username": username, "first_name": first},
            separators=(",", ":"),
        ),
        "auth_date": "1700000000",
    }
    if extra:
        params.update(extra)
    return _sign(params)


def test_validate_correct_init_data():
    assert validate_telegram_init_data(_make_init_data(), BOT_TOKEN) is True


def test_validate_with_signature_field():
    # Bot API 7.2+: signature входит в HMAC data_check_string
    assert (
        validate_telegram_init_data(
            _make_init_data(extra={"signature": "abcSIG"}), BOT_TOKEN
        )
        is True
    )


def test_validate_url_encoded_wrapper():
    raw = _make_init_data()
    wrapped = "tgWebAppData=" + quote(raw, safe="")
    assert validate_telegram_init_data(wrapped, BOT_TOKEN) is True


def test_validate_tampered_init_data():
    assert validate_telegram_init_data(_make_init_data() + "x", BOT_TOKEN) is False


def test_validate_wrong_token():
    assert validate_telegram_init_data(_make_init_data(), "999:wrong:token") is False


def test_validate_garbage():
    assert validate_telegram_init_data("not_a_init_data", BOT_TOKEN) is False


def test_get_user_profile_from_init_data():
    p = get_user_profile_from_init_data(
        _make_init_data(user_id=777, username="bob", first="Bob")
    )
    assert p["id"] == 777
    assert p["username"] == "bob"
    assert p["first_name"] == "Bob"


def test_profile_from_garbage():
    assert get_user_profile_from_init_data("garbage") == {}
