"""Динамический идентификатор бота.

Никнейм (@username) и id бота запрашиваются у Telegram один раз при старте
(через bot.get_me()) и хранятся как константы в памяти. Это исключает
хардкод @username в пользовательских строках (например /help@bot_name):
если ник бота изменится, ничего править в коде не нужно.

Использование:
    from shared.bot_identity import help_mention, get_bot_username, get_bot_id

    await init_bot_identity(bot)   # один раз при старте
    help_mention()                 # -> "/help@<bot_username>"
    get_bot_id()                   # -> 123456789 (для проверок «это сообщение бота»)
"""
import logging

logger = logging.getLogger(__name__)

_bot_username: str = ""
_bot_id: int = 0


async def init_bot_identity(bot) -> None:
    """Запросить у Telegram данные бота и сохранить в памяти."""
    global _bot_username, _bot_id
    me = await bot.get_me()
    _bot_username = me.username or ""
    _bot_id = me.id
    logger.info("Идентификация бота: @%s (id=%s)", _bot_username, _bot_id)


def get_bot_username() -> str:
    """@username бота без собаки."""
    return _bot_username


def get_bot_username_lower() -> str:
    """@username в нижнем регистре (для сравнений с message.from_user.username)."""
    return _bot_username.lower()


def get_bot_id() -> int:
    """Числовой id бота — надёжнее для проверок, чем username."""
    return _bot_id


def help_mention() -> str:
    """Строка вида `/help@bot_username` для упоминания команды в чате.

    Если ник ещё не получен (например, до старта), возвращает просто `/help`.
    """
    return f"/help@{_bot_username}" if _bot_username else "/help"


def is_bot_user(user_id: int | None = None, username: str | None = None) -> bool:
    """Проверить, является ли пользователь самим ботом.

    Сравнение по id надёжнее (username может измениться), но username
    используется как запасной вариант на случай, если идентификация ещё
    не инициализирована.
    """
    if user_id and _bot_id and user_id == _bot_id:
        return True
    if username and _bot_username and username.lower() == _bot_username.lower():
        return True
    return False


def reset() -> None:
    """Сброс (только для тестов)."""
    global _bot_username, _bot_id
    _bot_username = ""
    _bot_id = 0
