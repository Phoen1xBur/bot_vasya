from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from shared.config import get_settings

_settings = get_settings()


def build_inline_kb_start(chat_id: int, request_func: str, label: str) -> InlineKeyboardMarkup:
    """WebApp-кнопка в ЛС (profile/casino и т.д.)."""
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?{urlencode({'chat_id': chat_id, 'request_func': request_func})}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))]]
    )


def build_inline_kb_webapp(page: str, params: dict | None = None) -> InlineKeyboardMarkup:
    """Универсальная WebApp-кнопка для ЛС."""
    p = {"page": page}
    if params:
        p.update(params)
    url = f"{_settings.WEBAPP_BASE_URL}/webapp/index.html?{urlencode(p)}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть", web_app=WebAppInfo(url=url))]]
    )
