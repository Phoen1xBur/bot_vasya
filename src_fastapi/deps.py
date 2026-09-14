"""FastAPI-зависимости: авторизация WebApp через Telegram initData (HMAC-SHA256).

Все защищённые эндпоинты принимают initData из заголовка `X-Telegram-Init-Data`
или query-параметра `init_data`, проверяют подпись с помощью bot TOKEN и
возвращают профиль пользователя. Админ-эндпоинты дополнительно проверяют
user_id на вхождение в ADMIN_IDS из .env.
"""
import logging

from fastapi import HTTPException, Request, status

from shared.config import get_settings
from shared.telegram_auth import get_user_profile_from_init_data, validate_telegram_init_data

logger = logging.getLogger(__name__)
_settings = get_settings()


def _extract_init_data(request: Request) -> str:
    """Достаём initData из заголовка или query.

    Поддерживаемые источники (по приоритету):
    - заголовок X-Telegram-Init-Data
    - заголовок Authorization (raw-initData, либо с префиксом ``Telegram ``)
    - query-параметр init_data
    """
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        init_data = request.headers.get("X-Tg-Init-Data", "")
    if not init_data:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Telegram "):
            init_data = auth[len("Telegram ") :]
        elif auth and not auth.startswith(("Bearer ", "Basic ")):
            # WebApp-клиент шлёт raw initData в Authorization
            init_data = auth
    if not init_data:
        init_data = request.query_params.get("init_data", "")
    return init_data


async def require_telegram_user(request: Request) -> dict:
    """Обязательная авторизация: валидный initData от Telegram."""
    init_data = _extract_init_data(request)
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует Telegram initData",
        )
    if not validate_telegram_init_data(init_data, _settings.TOKEN):
        logger.warning("Неверная подпись initData")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверная подпись initData",
        )

    profile = get_user_profile_from_init_data(init_data)
    if not profile.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Не удалось определить пользователя",
        )
    return profile


async def require_admin_user(request: Request) -> dict:
    """Авторизация администратора: валидный initData + user_id в ADMIN_IDS."""
    profile = await require_telegram_user(request)
    if profile["id"] not in _settings.ADMIN_ID_SET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )
    return profile
