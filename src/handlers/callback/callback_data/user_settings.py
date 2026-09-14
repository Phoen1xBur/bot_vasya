"""Настройки пользователя (callback data factory — заглушка для обратной совместимости)."""
from aiogram.filters.callback_data import CallbackData


class UserSettings(CallbackData, prefix="profile"):
    action: str
    chat_id: int
