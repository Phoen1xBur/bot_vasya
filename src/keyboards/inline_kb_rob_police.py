from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_inline_kb_rob_police(user_id: int | str) -> InlineKeyboardMarkup:
    print(f'rob_police:yes:{user_id}')
    rows = [
        [InlineKeyboardButton(text='Да', callback_data=f'rob_police:yes:{user_id}')],
        [InlineKeyboardButton(text='Нет', callback_data=f'rob_police:no:{user_id}')],
        # InlineKeyboardButton('Отмена', callback_data='cancel'),
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
