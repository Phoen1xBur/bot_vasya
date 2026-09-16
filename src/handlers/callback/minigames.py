import logging
from urllib.parse import urlencode

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.deep_linking import create_start_link

from shared.config import get_settings
from shared.enums import GameType
from shared.models.game_room import GameRoomOrm
from shared.redis_client import get_redis
from run_bot import bot

_settings = get_settings()
router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("mg:select:"))
async def on_select_minigame(callback: CallbackQuery):
    """Выбор игры в чате → одна кнопка «Открыть игру в ЛС» с room id (без web_app в группе)."""
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

        game_param = {
            "ttt": "minigame_ttt",
            "roulette": "minigame_roulette",
            "slots": "minigame_slots",
        }.get(game, game)

        room_id = None
        room_note = ""
        if game == "roulette":
            # Создаём комнату сразу, чтобы в анонсе был уникальный id
            existing = await GameRoomOrm.get_active_for_user(creator_id)
            if (
                existing
                and existing.game_type == GameType.ROULETTE
                and int(existing.chat_id) == int(chat.id)
            ):
                room = existing
            else:
                if existing:
                    await callback.answer(
                        "У вас уже есть активная игра в другом чате",
                        show_alert=True,
                    )
                    return
                room = await GameRoomOrm.create(
                    game_type=GameType.ROULETTE,
                    chat_id=chat.id,
                    initiator_id=creator_id,
                    bet=0,
                    ttl_minutes=_settings.GAME_ROOM_TTL_MINUTES,
                )
            room_id = str(room.id)
            short = room_id.replace("-", "")[:8]
            room_note = f"\n🆔 Комната: <code>{short}</code>"
            try:
                get_redis().setex(
                    f"game:room:{room.id}",
                    _settings.GAME_ROOM_TTL_MINUTES * 60,
                    room_id,
                )
            except Exception:
                pass

        q = {"chat_id": chat.id, "request_func": game_param}
        if room_id:
            q["room"] = room_id
        deep_link = await create_start_link(bot, urlencode(q), encode=True)

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]
            ]
        )
        text = (
            f"🎰 Рулетка создана!{room_note}\nОткройте игру в личке с ботом:"
            if game == "roulette"
            else "Игра начинается! Откройте в личных сообщениях с ботом:"
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception:
        logger.exception("Ошибка выбора мини-игры")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:invite:"))
async def on_game_invite(callback: CallbackQuery):
    """Приглашение в игру — одна кнопка открытия в ЛС (с room при возможности)."""
    try:
        parts = callback.data.split(":")  # mg, invite, game_type, chat_id
        game_type = parts[2]
        chat_id = int(parts[3])

        q = {"chat_id": chat_id, "request_func": f"minigame_{game_type}"}
        # если у пользователя уже есть активная рулетка в этом чате — приложим room
        if game_type == "roulette":
            existing = await GameRoomOrm.get_active_for_user(callback.from_user.id)
            if existing and int(existing.chat_id) == chat_id:
                q["room"] = str(existing.id)

        deep_link = await create_start_link(bot, urlencode(q), encode=True)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]
            ]
        )
        await callback.message.edit_text(
            f"Игра «{game_type}» открыта! Одна кнопка — вход в ЛС:",
            reply_markup=kb,
        )
        await callback.answer()
    except Exception:
        logger.exception("Ошибка приглашения")
        await callback.answer("Произошла ошибка", show_alert=True)
