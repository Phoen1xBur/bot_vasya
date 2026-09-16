"""Фабрика callback-данных для настроек профиля в чате.

callback_data вида `profile:<action>:<chat_id>:<user_id>`:
- action — действие (toggle_tag)
- chat_id — чат настройки
- user_id — владелец профиля (только он может нажать)
"""
from aiogram.filters.callback_data import CallbackData


class UserSettings(CallbackData, prefix="profile"):
    action: str
    chat_id: int
    user_id: int
