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


def _webapp_url(page: str, chat_id: int, **extra: str) -> str:
    from urllib.parse import urlencode

    q = {"page": page, "chat_id": str(chat_id), **{k: str(v) for k, v in extra.items() if v is not None}}
    return f"{_settings.WEBAPP_BASE_URL}/webapp/?{urlencode(q)}"


@router.callback_query(F.data.startswith("mg:select:"))
async def on_select_minigame(callback: CallbackQuery):
    """Выбор мини-игры в чате."""
    try:
        chat = callback.message.chat if callback.message else None
        if not chat:
            await callback.answer("Ошибка: нет контекста чата", show_alert=True)
            return

        game = callback.data.split(":")[-1]
        creator_id = callback.from_user.id

        try:
            get_redis().hset(
                f"mg:lobby:{chat.id}",
                mapping={"creator_id": str(creator_id), "game": game},
            )
        except Exception:
            pass

        if game == "ttt":
            # Дуэль: ждём тег или reply от создателя
            try:
                get_redis().hset(
                    f"mg:ttt:picking:{chat.id}",
                    mapping={"creator_id": str(creator_id)},
                )
                get_redis().expire(f"mg:ttt:picking:{chat.id}", 180)
            except Exception:
                logger.exception("redis picking")

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Отменить",
                            callback_data=f"mg:ttt:pick_cancel:{chat.id}:{creator_id}",
                        )
                    ]
                ]
            )
            await callback.message.edit_text(
                "⚔️ Дуэль (крестики-нолики)\n\n"
                "Выберите оппонента:\n"
                "• тегните его (@username), или\n"
                "• ответьте на его сообщение любым текстом.\n\n"
                "В комнату смогут войти только вы и выбранный оппонент.",
                reply_markup=kb,
            )
            await callback.answer("Жду выбор оппонента")
            return

        # Рулетка / слоты — открываем WebApp в ЛС
        page = {"roulette": "roulette", "slots": "slots"}.get(game, game)
        url = _webapp_url(page, chat.id)
        sent_dm = False
        try:
            kb_dm = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎮 Открыть игру", web_app=WebAppInfo(url=url))]
                ]
            )
            await bot.send_message(
                creator_id,
                f"Игра «{page}» из чата — откройте Mini App:",
                reply_markup=kb_dm,
            )
            sent_dm = True
        except Exception:
            logger.warning("Не удалось отправить WebApp в ЛС user=%s", creator_id, exc_info=True)

        deep_link = await create_start_link(
            bot, _mg_start_payload(chat.id, f"minigame_{page}"), encode=True
        )
        rows = [[InlineKeyboardButton(text="🎮 Открыть игру в ЛС", url=deep_link)]]
        if page == "roulette":
            # До 8 игроков из чата — общая кнопка в чате
            rows.append(
                [InlineKeyboardButton(text="🎰 Присоединиться к рулетке", url=deep_link)]
            )
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        if sent_dm:
            text = (
                "Игра готова! Вам написал бот в ЛС."
                + (" Другие из чата могут присоединиться кнопкой ниже." if page == "roulette" else "")
            )
        else:
            text = (
                "Начните диалог с ботом (/start в ЛС), затем откройте игру кнопкой."
                + (" Кнопка ниже — для всех из чата." if page == "roulette" else "")
            )
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
    except Exception:
        logger.exception("Ошибка выбора мини-игры")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:invite:"))
async def on_game_invite(callback: CallbackQuery):
    """Приглашение в массовую игру."""
    try:
        parts = callback.data.split(":")
        game_type = parts[2]
        chat_id = int(parts[3])
        url = _webapp_url(game_type, chat_id)
        deep_link = await create_start_link(
            bot, _mg_start_payload(chat_id, f"minigame_{game_type}"), encode=True
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎮 Присоединиться", url=deep_link)]]
        )
        await callback.message.edit_text(
            f"Игра «{game_type}» открыта! Присоединяйтесь (через ЛС с ботом):",
            reply_markup=kb,
        )
        await callback.answer()
    except Exception:
        logger.exception("Ошибка приглашения")
        await callback.answer("Произошла ошибка", show_alert=True)
