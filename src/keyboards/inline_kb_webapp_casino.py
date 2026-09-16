from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from shared.config import get_settings

_settings = get_settings()


def build_inline_kb_webapp_casino(chat_id: int | None = None) -> InlineKeyboardMarkup:
    """Кнопка входа в казино (WebApp) — только в ЛС; chat_id группы нужен для баланса."""
    base = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=casino"
    if chat_id is not None:
        url = f"{base}&chat_id={int(chat_id)}"
    else:
        url = base
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎰 Открыть казино", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_admin() -> InlineKeyboardMarkup:
    """Кнопка админ-панели (WebApp) — только в ЛС, только для админов."""
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=admin"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛠 Админ-панель", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_advertise() -> InlineKeyboardMarkup:
    """Кнопка рекламы (WebApp) — только в ЛС."""
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=advertise"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Создать рекламу", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_profile(chat_id: int) -> InlineKeyboardMarkup:
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=profile&chat_id={chat_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👤 Профиль", web_app=WebAppInfo(url=url))]]
    )
