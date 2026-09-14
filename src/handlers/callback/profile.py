import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from shared.models.group_user import GroupUserOrm

router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("profile:toggle_tag:"))
async def toggle_tag(callback: CallbackQuery):
    """Включить/выключить тег участника в чате."""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[-1])
        user_id = callback.from_user.id
        can_tag = await GroupUserOrm.change_can_tag(user_id, chat_id)
        label = "❌ Выключить тег" if can_tag else "✅ Включить тег"
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"profile:toggle_tag:{chat_id}")]]
        )
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer(f"Тег {'включён' if can_tag else 'выключен'}")
    except Exception:
        logger.exception("Ошибка toggle_tag")
        await callback.answer("Произошла ошибка", show_alert=True)
