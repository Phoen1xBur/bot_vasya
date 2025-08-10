from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from handlers.callback.callback_data.user_settings import UserSettings, Action


async def profile_change_settings(user_id: int | str, chat_id: int | str, notification: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f'{notification} уведомления',
                callback_data=UserSettings(
                    action=Action.notify,
                    tg_user_id=user_id, tg_chat_id=chat_id
                ).pack()
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
