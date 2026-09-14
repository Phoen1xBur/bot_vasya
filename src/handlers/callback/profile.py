import logging

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shared.models.group_user import GroupUserOrm
from handlers.callback.callback_data.user_settings import UserSettings

router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.callback_query(UserSettings.filter(F.action == "toggle_tag"))
async def toggle_tag(callback: CallbackQuery, callback_data: UserSettings):
    """Включить/выключить тег участника в чате."""
    try:
        chat_id = callback_data.chat_id
        user_id = callback.from_user.id
        can_tag = await GroupUserOrm.change_can_tag(user_id, chat_id)
        label = "❌ Выключить тег" if can_tag else "✅ Включить тег"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=UserSettings(action="toggle_tag", chat_id=chat_id).pack(),
                    )
                ]
            ]
        )
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer(f"Тег {'включён' if can_tag else 'выключен'}")
    except Exception:
        logger.exception("Ошибка toggle_tag")
        await callback.answer("Произошла ошибка", show_alert=True)
