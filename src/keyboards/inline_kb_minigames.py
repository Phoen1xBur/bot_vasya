from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_kb_minigames_select() -> InlineKeyboardMarkup:
    """Меню выбора мини-игры (в чате — обычные inline-кнопки, без web_app)."""
    rows = [
        [InlineKeyboardButton(text="❌ Крестики-нолики (дуэль)", callback_data="mg:select:ttt")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="mg:select:roulette")],
        [InlineKeyboardButton(text="🔔 Слот-машина", callback_data="mg:select:slots")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
