import logging
from urllib.parse import urlencode

from aiogram import F, Bot, Router
from aiogram.enums import MessageEntityType
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)

from shared.config import get_settings
from shared.enums import ChatType, GameType
from shared.models.game_room import GameRoomOrm
from shared.redis_client import get_redis
from aiogram.filters import BaseFilter
from utils.filters import ChatTypeFilter

router = Router(name=__name__)
logger = logging.getLogger(__name__)
_settings = get_settings()


def _room_key(chat_id: int) -> str:
    return f"mg:ttt:room:{chat_id}"


def _picking_key(chat_id: int) -> str:
    return f"mg:ttt:picking:{chat_id}"



class TttPickingFilter(BaseFilter):
    """Срабатывает только пока создатель выбирает оппонента (иначе глотает все group-сообщения)."""

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        try:
            raw = get_redis().hgetall(_picking_key(message.chat.id))
        except Exception:
            return False
        if not raw:
            return False
        cid = raw.get("creator_id", raw.get(b"creator_id"))
        if cid is None:
            return False
        cid_s = cid.decode() if isinstance(cid, bytes) else str(cid)
        return str(message.from_user.id) == cid_s


def _webapp_ttt_url(chat_id: int, room_id: str, target_id: int) -> str:
    q = urlencode(
        {
            "page": "ttt",
            "chat_id": str(chat_id),
            "room": str(room_id),
            "target": str(target_id),
        }
    )
    return f"{_settings.WEBAPP_BASE_URL}/webapp/?{q}"


async def _resolve_opponent(message: Message, bot: Bot) -> User | None:
    """Оппонент из reply или упоминания."""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        if not u.is_bot:
            return u

    if not message.entities or not message.text:
        return None

    for ent in message.entities:
        if ent.type == MessageEntityType.TEXT_MENTION and ent.user and not ent.user.is_bot:
            return ent.user
        if ent.type == MessageEntityType.MENTION:
            raw = message.text[ent.offset : ent.offset + ent.length]
            username = raw.lstrip("@")
            if not username:
                continue
            try:
                chat = await bot.get_chat(f"@{username}")
                if getattr(chat, "type", None) == "private" or getattr(chat, "id", None):
                    # get_chat returns Chat; build minimal User-like via get_chat_member if in group
                    try:
                        member = await bot.get_chat_member(message.chat.id, chat.id)
                        if member.user and not member.user.is_bot:
                            return member.user
                    except Exception:
                        # fallback: synthetic check with chat.id
                        from aiogram.types import User as TgUser

                        return TgUser(
                            id=chat.id,
                            is_bot=False,
                            first_name=getattr(chat, "first_name", None) or username,
                            username=getattr(chat, "username", None) or username,
                        )
            except Exception:
                logger.info("Не удалось резолвить @%s", username, exc_info=True)
    return None


async def _send_duel_links(
    bot: Bot, chat_id: int, creator_id: int, opponent_id: int, room_id: str
) -> None:
    url = _webapp_ttt_url(chat_id, room_id, opponent_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Открыть дуэль", web_app=WebAppInfo(url=url))]
        ]
    )
    for uid, text in (
        (creator_id, "⚔️ Дуэль создана! Откройте игру (вы — крестики):"),
        (opponent_id, "⚔️ Вас вызвали на дуэль! Откройте игру (вы — нолики):"),
    ):
        try:
            await bot.send_message(uid, text, reply_markup=kb)
        except Exception:
            logger.warning("Не удалось отправить дуэль в ЛС user=%s", uid, exc_info=True)


@router.callback_query(F.data.startswith("mg:ttt:pick_cancel:"))
async def on_ttt_pick_cancel(callback: CallbackQuery):
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        if callback.from_user.id != creator_id:
            await callback.answer("Отменить может только создатель", show_alert=True)
            return
        try:
            get_redis().delete(_picking_key(chat_id))
        except Exception:
            pass
        if callback.message:
            await callback.message.edit_text("Выбор оппонента отменён.")
        await callback.answer("Отменено")
    except Exception:
        logger.exception("Ошибка pick_cancel TTT")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("mg:ttt:cancel:"))
async def on_ttt_cancel(callback: CallbackQuery):
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        user_id = callback.from_user.id
        if user_id != creator_id:
            await callback.answer("Вы не создатель комнаты", show_alert=True)
            return
        try:
            get_redis().delete(_room_key(chat_id))
            get_redis().delete(_picking_key(chat_id))
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
    """Принятие дуэли — только назначенный оппонент (если ещё используется)."""
    try:
        parts = callback.data.split(":")
        chat_id = int(parts[3])
        creator_id = int(parts[4])
        user_id = callback.from_user.id

        if user_id == creator_id:
            await callback.answer("Вы создатель дуэли — дождитесь противника", show_alert=True)
            return

        target_id = None
        try:
            raw = get_redis().hget(_room_key(chat_id), "target_id")
            if raw is not None:
                target_id = int(raw.decode() if isinstance(raw, bytes) else raw)
        except Exception:
            pass

        if target_id is not None and user_id != target_id:
            await callback.answer("Вы не приглашены в эту дуэль", show_alert=True)
            return

        try:
            get_redis().hset(
                _room_key(chat_id),
                mapping={"player2_id": str(user_id), "target_id": str(user_id), "state": "active"},
            )
        except Exception:
            pass

        # Комната в БД
        existing = await GameRoomOrm.get_active_for_user(creator_id)
        if existing and existing.chat_id == chat_id and existing.game_type == GameType.TTT:
            room = existing
            if room.target_id and room.target_id != user_id:
                await callback.answer("Вы не приглашены в эту дуэль", show_alert=True)
                return
            if not room.target_id:
                await GameRoomOrm.update(str(room.id), target_id=user_id)
        else:
            room = await GameRoomOrm.create(
                game_type=GameType.TTT,
                chat_id=chat_id,
                initiator_id=creator_id,
                target_id=user_id,
                bet=0,
                ttl_minutes=_settings.GAME_ROOM_TTL_MINUTES,
            )
            await GameRoomOrm.update(str(room.id), state={"board": " " * 9, "turn": "X"})

        await _send_duel_links(callback.bot, chat_id, creator_id, user_id, str(room.id))
        if callback.message:
            await callback.message.edit_text("⚔️ Дуэль началась! Проверьте личные сообщения.")
        await callback.answer()
    except Exception:
        logger.exception("Ошибка accept TTT")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(ChatTypeFilter(ChatType.GROUP, ChatType.SUPERGROUP), TttPickingFilter())
async def on_ttt_pick_opponent(message: Message, bot: Bot):
    """Пока создатель выбирает оппонента — ловим тег/reply."""
    if not message.from_user:
        return
    try:
        raw = get_redis().hgetall(_picking_key(message.chat.id))
    except Exception:
        return
    if not raw:
        return

    def _g(key: str) -> str | None:
        if key in raw:
            v = raw[key]
        elif key.encode() in raw:
            v = raw[key.encode()]
        else:
            return None
        return v.decode() if isinstance(v, bytes) else str(v)

    creator_s = _g("creator_id")
    if not creator_s:
        return
    creator_id = int(creator_s)
    if message.from_user.id != creator_id:
        return

    opponent = await _resolve_opponent(message, bot)
    if opponent is None:
        await message.reply(
            "Не вижу оппонента. Тегните его (@username) или ответьте на его сообщение."
        )
        return
    if opponent.id == creator_id:
        await message.reply("Нельзя вызвать на дуэль самого себя.")
        return

    try:
        get_redis().delete(_picking_key(message.chat.id))
    except Exception:
        pass

    # Одна активная комната на пользователя
    for uid in (creator_id, opponent.id):
        existing = await GameRoomOrm.get_active_for_user(uid)
        if existing:
            await message.reply(
                "У вас или у оппонента уже есть активная игра. Завершите её или дождитесь истечения."
            )
            return

    room = await GameRoomOrm.create(
        game_type=GameType.TTT,
        chat_id=message.chat.id,
        initiator_id=creator_id,
        target_id=opponent.id,
        bet=0,
        ttl_minutes=_settings.GAME_ROOM_TTL_MINUTES,
    )
    await GameRoomOrm.update(str(room.id), state={"board": " " * 9, "turn": "X"})

    try:
        get_redis().hset(
            _room_key(message.chat.id),
            mapping={
                "creator_id": str(creator_id),
                "target_id": str(opponent.id),
                "room_id": str(room.id),
                "state": "waiting",
            },
        )
        get_redis().expire(_room_key(message.chat.id), _settings.GAME_ROOM_TTL_MINUTES * 60)
    except Exception:
        pass

    mention_opp = opponent.mention_html() if hasattr(opponent, "mention_html") else (
        f'<a href="tg://user?id={opponent.id}">{opponent.full_name or opponent.first_name}</a>'
    )
    await message.answer(
        f"⚔️ Дуэль создана: вы против {mention_opp}.\n"
        "В комнату могут войти только вы двое. Проверьте ЛС с ботом — там кнопка «Открыть дуэль».",
        parse_mode="HTML",
    )
    await _send_duel_links(bot, message.chat.id, creator_id, opponent.id, str(room.id))
