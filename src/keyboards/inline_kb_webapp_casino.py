from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from shared.config import get_settings

_settings = get_settings()


def build_inline_kb_webapp_casino() -> InlineKeyboardMarkup:
    """Кнопка входа в казино (WebApp) — только в ЛС!"""
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?page=casino"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎰 Открыть казино", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_admin() -> InlineKeyboardMarkup:
    """Кнопка админ-панели (WebApp) — только в ЛС, только для админов."""
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?page=admin"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🛠 Админ-панель", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_advertise() -> InlineKeyboardMarkup:
    """Кнопка подачи рекламы (WebApp) — только в ЛС."""
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?page=advertise"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📢 Подать рекламу", web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp_profile(chat_id: int) -> InlineKeyboardMarkup:
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?page=profile&chat_id={chat_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📱 Профиль", web_app=WebAppInfo(url=url))]]
    )
