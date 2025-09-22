from aiogram.types import InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton


def build_inline_kb_webapp_casino() -> InlineKeyboardMarkup:
    webapp = WebAppInfo(url='https://ija3ye-109-196-195-44.ru.tuna.am/casino/main?chat_id=123')

    rows = [
        [InlineKeyboardButton(text='Открыть персональную страницу', web_app=webapp)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
