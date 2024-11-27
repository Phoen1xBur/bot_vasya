from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_inline_kb_rob_police() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text='Да', callback_data='yes')],
        [InlineKeyboardButton(text='Нет', callback_data='no')],
        # InlineKeyboardButton('Отмена', callback_data='cancel'),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
