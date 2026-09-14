from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_kb_subscribe() -> InlineKeyboardMarkup:
    """Кнопки выбора уровня подписки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ VIP — 199₽/мес", callback_data="sub:buy:vip")],
            [InlineKeyboardButton(text="💎 Premium — 399₽/мес", callback_data="sub:buy:premium")],
            [InlineKeyboardButton(text="👑 Elite — 799₽/мес", callback_data="sub:buy:elite")],
            [InlineKeyboardButton(text="Отмена автопродления", callback_data="sub:cancel")],
        ]
    )


def build_inline_kb_donate() -> InlineKeyboardMarkup:
    """Фиксированные суммы доната + своя."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="50₽", callback_data="donate:50"),
                InlineKeyboardButton(text="100₽", callback_data="donate:100"),
            ],
            [
                InlineKeyboardButton(text="300₽", callback_data="donate:300"),
                InlineKeyboardButton(text="500₽", callback_data="donate:500"),
            ],
            [
                InlineKeyboardButton(text="1000₽", callback_data="donate:1000"),
                InlineKeyboardButton(text="Своя сумма", callback_data="donate:custom"),
            ],
        ]
    )
