from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.models.group_user import GroupUserOrm


async def profile_change_settings(user_id: int, tg_chat_id: int, notification: str) -> InlineKeyboardMarkup:
    group_user = await GroupUserOrm.get_group_user(user_id, tg_chat_id)
    can_tag = group_user.can_tag if group_user else True
    label = "❌ Выключить тег" if can_tag else "✅ Включить тег"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"profile:toggle_tag:{tg_chat_id}")]
        ]
    )
