import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from shared.redis_client import get_redis

router = Router(name=__name__)
logger = logging.getLogger(__name__)


def _room_key(chat_id: int) -> str:
    return f"mg:ttt:room:{chat_id}"


@router.callback_query(F.data.startswith("mg:ttt:cancel:"))
async def on_ttt_cancel(callback: CallbackQuery):
    try:
        parts = callback.data.split(":")  # mg, ttt, cancel, chat_id, creator_id
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        user_id = callback.from_user.id
        if user_id != creator_id:
            await callback.answer("Вы не создатель комнаты", show_alert=True)
            return
        try:
            get_redis().delete(_room_key(chat_id))
        except Exception:
            pass
        if callback.message:
            await callback.message.edit_text("Игра отменена создателем")
        await callback.answer("Игра отменена")
    except Exception:
        logger.exception("Ошибка отмены TTT")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:ttt:accept:"))
async def on_ttt_accept(callback: CallbackQuery):
    """Принятие дуэли — отправляем обоим в ЛС web_app-кнопку."""
    try:
        parts = callback.data.split(":")  # mg, ttt, accept, chat_id, creator_id
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        user_id = callback.from_user.id

        if user_id == creator_id:
            await callback.answer("Вы создатель дуэли — дождитесь противника", show_alert=True)
            return

        # Регистрируем второго игрока
        try:
            get_redis().hset(
                _room_key(chat_id),
                mapping={"player2_id": user_id, "state": "active"},
            )
        except Exception:
            pass

        from urllib.parse import urlencode

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        from aiogram.utils.deep_linking import create_start_link

        from shared.config import get_settings

        _s = get_settings()
        # Отправляем обоим в ЛС ссылку на web_app
        for uid in (creator_id, user_id):
            try:
                url = f"{_s.WEBAPP_BASE_URL}/webapp/index.html?page=ttt&chat_id={chat_id}"
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="❌ Открыть дуэль", web_app=WebAppInfo(url=url))]]
                )
                await callback.bot.send_message(uid, "⚔️ Дуэль началась! Откройте игру:", reply_markup=kb)
            except Exception:
                logger.warning("Не удалось отправить дуэль в ЛС user=%s", uid)

        if callback.message:
            await callback.message.edit_text("⚔️ Дуэль началась! Проверьте личные сообщения.")
        await callback.answer()
    except Exception:
        logger.exception("Ошибка accept TTT")
        await callback.answer("Произошла ошибка", show_alert=True)
