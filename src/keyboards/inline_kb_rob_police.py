from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_kb_rob_police(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура взаимодействия с полицией при ограблении."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💸 Дать взятку", callback_data=f"rob:bribe:{user_id}"),
                InlineKeyboardButton(text="🚔 Сдаться", callback_data=f"rob:surrender:{user_id}"),
            ]
        ]
    )
