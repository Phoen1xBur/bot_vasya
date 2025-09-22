from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def build_inline_kb_minigames_select() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text='Крестики-нолики', callback_data='mg:select:ttt'),
        ],
        [
            InlineKeyboardButton(text='Казино — рулетка', callback_data='mg:select:roulette'),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


