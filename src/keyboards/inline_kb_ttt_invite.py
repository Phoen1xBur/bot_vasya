from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_kb_ttt_invite(chat_id: int, creator_id: int, joined: int = 0) -> InlineKeyboardMarkup:
    """Приглашение в крестики-нолики (дуэль).

    callback_data: mg:ttt:accept:{chat_id}:{creator_id}
    """
    rows = [
        [InlineKeyboardButton(text="⚔️ Принять дуэль", callback_data=f"mg:ttt:accept:{chat_id}:{creator_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"mg:ttt:cancel:{chat_id}:{creator_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_inline_kb_game_invite(chat_id: int, game_type: str, label: str = "Играть") -> InlineKeyboardMarkup:
    """Универсальная кнопка приглашения в игру (в чате — без web_app)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"mg:invite:{game_type}:{chat_id}")]
        ]
    )
