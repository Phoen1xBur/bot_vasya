from urllib.parse import urlencode

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_start_link

from run import bot


async def build_inline_kb_ttt_invite(chat_id: int, creator_id: int, joined: int = 0) -> InlineKeyboardMarkup:
    params = {
        'chat_id': chat_id,
        'request_func': 'minigame_ttt',
    }
    deep_link = await create_start_link(bot, urlencode(params), encode=True)

    rows = [
        [InlineKeyboardButton(text=f'Зайти в комнату [{joined}/2]', url=deep_link)],
        [InlineKeyboardButton(text='Отмена игры', callback_data=f'mg:ttt:cancel:{chat_id}:{creator_id}')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


