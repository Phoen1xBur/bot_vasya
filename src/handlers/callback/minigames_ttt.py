import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import redis


router = Router(name=__name__)


def _room_key(chat_id: int) -> str:
    return f'mg:ttt:room:{chat_id}'


@router.callback_query(F.data.startswith('mg:ttt:cancel:'))
async def on_ttt_cancel(callback: CallbackQuery):
    logger = logging.getLogger(__name__)
    try:
        parts = callback.data.split(':')  # mg, ttt, cancel, chat_id, creator_id
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        user_id = callback.from_user.id
        if user_id != creator_id:
            await callback.answer('Вы не создатель комнаты', show_alert=True)
            return

        # Проверяем, что комната принадлежит этому чату и создателю
        data = redis.hgetall(_room_key(chat_id))
        if not data or str(data.get('creator_id')) != str(creator_id):
            await callback.answer('Комната не найдена', show_alert=True)
            return

        redis.delete(_room_key(chat_id))
        if callback.message:
            await callback.message.edit_text('Игра отменена создателем')
        await callback.answer('Игра отменена', show_alert=False)
    except Exception as e:
        logger.exception('Ошибка при отмене TTT: %s', e)
        await callback.answer('Произошла ошибка', show_alert=True)


