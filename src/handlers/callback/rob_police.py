import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from shared.models.money import Prison

router = Router(name=__name__)
logger = logging.getLogger(__name__)


def _intended_user_id(data: str) -> int | None:
    parts = (data or "").split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


@router.callback_query(F.data.startswith("rob:bribe:"))
async def on_rob_bribe(callback: CallbackQuery):
    """Дать взятку полиции — только тому, кого поймали."""
    user_id = callback.from_user.id
    intended = _intended_user_id(callback.data or "")
    if intended is not None and user_id != intended:
        await callback.answer("Это не ваша кнопка", show_alert=True)
        return
    chat_id = callback.message.chat.id if callback.message else 0
    try:
        from shared.models.group_user import GroupUserOrm

        group_user = await GroupUserOrm.get_group_user(user_id, chat_id)
        if group_user and group_user.money >= 200:
            await group_user.money_minus(200)
            Prison.free_prisoner(chat_id, user_id)
            await callback.answer("Вы дали взятку и освобождены! −200 васякоинов", show_alert=True)
            if callback.message:
                await callback.message.edit_text("🤝 Вы дали взятку полиции и свободны.")
        else:
            await callback.answer("Недостаточно васякоинов для взятки (нужно 200)", show_alert=True)
    except Exception:
        logger.exception("Ошибка взятки")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("rob:surrender:"))
async def on_rob_surrender(callback: CallbackQuery):
    """Сдаться полиции — только тот, кого поймали."""
    user_id = callback.from_user.id
    intended = _intended_user_id(callback.data or "")
    if intended is not None and user_id != intended:
        await callback.answer("Это не ваша кнопка", show_alert=True)
        return
    chat_id = callback.message.chat.id if callback.message else 0
    try:
        Prison.free_prisoner(chat_id, user_id)
        await callback.answer("Вы отсидели... почти.", show_alert=False)
        if callback.message:
            await callback.message.edit_text("🚔 Вы сдались полиции. Тюрьма отменена (тест).")
    except Exception:
        logger.exception("Ошибка сдачи")
        await callback.answer("Произошла ошибка", show_alert=True)
