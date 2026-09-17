import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shared.config import get_settings
from shared.enums import GameRoomStatus, GameType
from shared.models.game_room import GameRoomOrm
from shared.redis_client import get_redis
from utils.deeplink import create_dm_start_link, remember_room_short
from run_bot import bot

_settings = get_settings()
router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("mg:select:"))
async def on_select_minigame(callback: CallbackQuery):
    """Выбор игры в чате: TTT — тег соперника; остальные — открыть в ЛС."""
    try:
        chat = callback.message.chat if callback.message else None
        if not chat:
            await callback.answer("Ошибка: нет контекста чата", show_alert=True)
            return

        game = callback.data.split(":")[-1]
        creator_id = callback.from_user.id

        try:
            get_redis().hset(f"mg:lobby:{chat.id}", mapping={"creator_id": creator_id})
        except Exception:
            pass

        if game == "ttt":
            try:
                r = get_redis()
                key = f"mg:ttt:picking:{chat.id}"
                r.hset(key, mapping={"creator_id": str(creator_id)})
                r.expire(key, 300)
            except Exception:
                logger.exception("не удалось включить TTT picking")
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Отмена",
                            callback_data=f"mg:ttt:pick_cancel:{chat.id}:{creator_id}",
                        )
                    ]
                ]
            )
            await callback.message.edit_text(
                "⚔️ <b>Крестики-нолики</b>\n"
                "Тегни соперника (@username) или ответь <b>реплаем</b> на его сообщение.",
                reply_markup=kb,
                parse_mode="HTML",
            )
            await callback.answer()
            return

        game_param = {
            "roulette": "minigame_roulette",
            "slots": "minigame_slots",
            "blackjack": "minigame_blackjack",
        }.get(game, game)

        room_id = None
        room_note = ""
        if game == "roulette":
            try:
                await GameRoomOrm.expire_overdue()
            except Exception:
                pass
            room = await GameRoomOrm.create(
                game_type=GameType.ROULETTE,
                chat_id=chat.id,
                initiator_id=creator_id,
                bet=0,
                ttl_minutes=_settings.GAME_ROOM_TTL_MINUTES,
            )
            room_id = str(room.id)
            short = remember_room_short(room_id)
            room_note = f"\n🆔 Комната: <code>{short}</code>"

        deep_link = await create_dm_start_link(
            bot,
            request_func=game_param,
            chat_id=chat.id,
            room_id=room_id,
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]
            ]
        )
        text = (
            f"🎰 Рулетка создана!{room_note}\nОткройте игру в личке с ботом:"
            if game == "roulette"
            else "Игра начинается! Откройте в личном сообщении с ботом:"
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception:
        logger.exception("Ошибка выбора мини-игры")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:invite:"))
async def on_game_invite(callback: CallbackQuery):
    """Приглашение в игру — кнопка открыть в ЛС."""
    try:
        parts = callback.data.split(":")  # mg, invite, game_type, chat_id
        game_type = parts[2]
        chat_id = int(parts[3])

        room_id = None

        deep_link = await create_dm_start_link(
            bot,
            request_func=f"minigame_{game_type}",
            chat_id=chat_id,
            room_id=room_id,
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]
            ]
        )
        await callback.message.edit_text(
            f"Игра «{game_type}» открыта! Одна кнопка — прямо в ЛС:",
            reply_markup=kb,
        )
        await callback.answer()
    except Exception:
        logger.exception("Ошибка приглашения")
        await callback.answer("Произошла ошибка", show_alert=True)
