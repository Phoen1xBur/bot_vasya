import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.deep_linking import create_start_link

from shared.config import get_settings
from shared.redis_client import get_redis
from run_bot import bot

_settings = get_settings()
router = Router(name=__name__)
logger = logging.getLogger(__name__)

# Telegram start payload limit is 64 chars; urlencode+base64 of full keys overflows.
_GAME_SHORT = {
    "ttt": "ttt",
    "roulette": "roulette",
    "slots": "slots",
    "minigame_ttt": "ttt",
    "minigame_roulette": "roulette",
    "minigame_slots": "slots",
}


def _mg_start_payload(chat_id: int, game: str) -> str:
    short = _GAME_SHORT.get(game, game.replace("minigame_", ""))
    payload = f"c={chat_id}&f={short}"
    if len(payload) > 64:
        raise ValueError(f"start payload too long ({len(payload)}): {payload!r}")
    return payload



@router.callback_query(F.data.startswith("mg:select:"))
async def on_select_minigame(callback: CallbackQuery):
    """Выбор игры в чате → отправляем в ЛС кнопку с web_app (обход ограничения)."""
    try:
        chat = callback.message.chat if callback.message else None
        if not chat:
            await callback.answer("Ошибка: нет контекста чата", show_alert=True)
            return

        game = callback.data.split(":")[-1]
        creator_id = callback.from_user.id

        # Сохраняем лобби
        try:
            get_redis().hset(f"mg:lobby:{chat.id}", mapping={"creator_id": creator_id})
        except Exception:
            pass

        # Глубокая ссылка в ЛС бота с параметром игры
        game_param = {
            "ttt": "minigame_ttt",
            "roulette": "minigame_roulette",
            "slots": "minigame_slots",
        }.get(game, game)

        deep_link = await create_start_link(
            bot, _mg_start_payload(chat.id, game_param), encode=True
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]]
        )
        await callback.message.edit_text(
            "Игра начинается! Проверьте личные сообщения от бота.",
            reply_markup=kb,
        )
        await callback.answer()
    except Exception:
        logger.exception("Ошибка выбора мини-игры")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:invite:"))
async def on_game_invite(callback: CallbackQuery):
    """Приглашение участников в массовую игру (рулетка)."""
    try:
        parts = callback.data.split(":")  # mg, invite, game_type, chat_id
        game_type = parts[2]
        chat_id = int(parts[3])
        creator_id = callback.from_user.id

        deep_link = await create_start_link(
            bot, _mg_start_payload(chat_id, f"minigame_{game_type}"), encode=True
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎮 Присоединиться", url=deep_link)]]
        )
        await callback.message.edit_text(
            f"Игра «{game_type}» открыта! Присоединяйтесь:",
            reply_markup=kb,
        )
        await callback.answer()
    except Exception:
        logger.exception("Ошибка приглашения")
        await callback.answer("Произошла ошибка", show_alert=True)
