"""Фабрика callback-данных для настроек профиля в чате.

callback_data вида `profile:<action>:<chat_id>`:
- action — действие над настройкой (toggle_tag).
- chat_id — чат, к которому относится настройка.

Используется клавиатурой `inline_kb_profile_change_settings` и
callback-обработчиком `handlers/callback/profile`.
"""
from aiogram.filters.callback_data import CallbackData


class UserSettings(CallbackData, prefix="profile"):
    action: str
    chat_id: int
