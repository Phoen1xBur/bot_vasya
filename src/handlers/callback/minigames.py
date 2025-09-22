import logging
from urllib.parse import urlencode

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.deep_linking import create_start_link

from config import redis
from run import bot
from keyboards.inline_kb_ttt_invite import build_inline_kb_ttt_invite


router = Router(name=__name__)


def _key_ttt(chat_id: int) -> str:
    return f'mg:ttt:room:{chat_id}'


def _key_roulette(chat_id: int) -> str:
    return f'mg:roulette:room:{chat_id}'


@router.callback_query(F.data.startswith('mg:select:'))
async def on_select_minigame(callback: CallbackQuery):
    logger = logging.getLogger(__name__)
    try:
        chat = callback.message.chat if callback.message else None
        if not chat:
            await callback.answer('Ошибка: отсутствует контекст чата', show_alert=True)
            return

        game = callback.data.split(':')[-1]
        creator_id = callback.from_user.id

        if game == 'ttt':
            # Создатель берётся из лобби, если есть
            lobby = redis.hgetall(f'mg:lobby:{chat.id}')
            room_creator = int(lobby.get('creator_id', creator_id) or creator_id)
            redis.hset(_key_ttt(chat.id), mapping={
                'creator_id': room_creator,
                'player2_id': 0,
                'bet_creator': 0,
                'bet_player2': 0,
                'state': 'waiting',  # waiting, betting, playing, finished
            })
            kb = await build_inline_kb_ttt_invite(chat.id, room_creator, joined=0)
            await callback.message.edit_text('Крестики-нолики: приглашение в игру', reply_markup=kb)
            await callback.answer()
            return

        if game == 'roulette':
            # Создаём комнату, если ещё нет
            room_key = _key_roulette(chat.id)
            if not redis.exists(room_key):
                lobby = redis.hgetall(f'mg:lobby:{chat.id}')
                room_creator = int(lobby.get('creator_id', creator_id) or creator_id)
                redis.hset(room_key, mapping={
                    'creator_id': room_creator,
                    'state': 'open',  # open, spinning, finished
                })
            # Даём ссылку в ЛС
            params = {
                'chat_id': chat.id,
                'request_func': 'minigame_roulette',
            }
            deep_link = await create_start_link(bot, urlencode(params), encode=True)
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Перейти в ЛС', url=deep_link)]])
            await callback.message.edit_text('Рулетка: переходите в ЛС для входа в игру', reply_markup=kb)
            await callback.answer()
            return

        await callback.answer('Неизвестная игра', show_alert=True)
    except Exception as e:
        logger.exception('Ошибка при выборе мини-игры: %s', e)
        await callback.answer('Произошла ошибка', show_alert=True)


