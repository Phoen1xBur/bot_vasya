from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.deep_linking import create_start_link

from run import bot


async def build_inline_kb_start(chat_id: int, request_func: str, request_description: str) -> InlineKeyboardMarkup:
    """
    Возвращает inline-клавиатуру со ссылкой на старт бота с
    :param chat_id: ID чата откуда инициализация запроса
    :param request_func: наименование запроса (profile/casino e.t.c)
    :param request_description: Название кнопки для отображения
    :return: Markup клавиатура для сообщения (reply_markup)
    """
    # Формируем параметры для deep link
    params = {
        'chat_id': chat_id,
        'request_func': request_func,
    }
    deep_link = await create_start_link(bot, urlencode(params), encode=True)

    rows = [
        [InlineKeyboardButton(text=request_description, url=deep_link)],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)
