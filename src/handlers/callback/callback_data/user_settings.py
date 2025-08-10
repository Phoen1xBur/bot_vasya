from enum import Enum

from aiogram.filters.callback_data import CallbackData


class Action(str, Enum):
    notify = "Notify"


class UserSettings(CallbackData, prefix="user"):
    action: Action
    tg_user_id: int
    tg_chat_id: int
