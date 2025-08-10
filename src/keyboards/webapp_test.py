from urllib.parse import urlencode

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.deep_linking import create_start_link

from run import bot


def build_inline_kb_webapp() -> InlineKeyboardMarkup:
    webapp = WebAppInfo(url='https://m7z9za-178-155-17-223.ru.tuna.am/me')

    rows = [
        [InlineKeyboardButton(text='Открыть персональную страницу', web_app=webapp)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_inline_kb_start(chat_id: int, request_func: str) -> InlineKeyboardMarkup:
    # Формируем параметры для deep link
    params = {
        'chat_id': chat_id,
        'request_func': request_func,
    }
    deep_link = await create_start_link(bot, urlencode(params), encode=True)

    rows = [
        [InlineKeyboardButton(text="📱 Открыть профиль", url=deep_link)],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)
