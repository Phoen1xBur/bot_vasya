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


async def _lookup_username_in_db(chat_id: int, username: str) -> int | None:
    """Ищем user_id по username в UserOrm / GroupUserOrm (case-insensitive)."""
    from sqlalchemy import func, select

    from shared.database import async_session_factory
    from shared.models.group_user import GroupUserOrm
    from shared.models.user import UserOrm

    uname = username.lstrip("@").strip()
    if not uname:
        return None
    async with async_session_factory() as session:
        q = (
            select(UserOrm.user_id)
            .join(GroupUserOrm, GroupUserOrm.user_id == UserOrm.user_id)
            .where(
                GroupUserOrm.telegram_chat_id == chat_id,
                func.lower(UserOrm.username) == uname.lower(),
            )
            .limit(1)
        )
        row = (await session.execute(q)).first()
        if row:
            return int(row[0])
        q2 = (
            select(UserOrm.user_id)
            .where(func.lower(UserOrm.username) == uname.lower())
            .limit(1)
        )
        row2 = (await session.execute(q2)).first()
        if row2:
            return int(row2[0])
    return None


async def _resolve_opponent(message: Message, bot: Bot) -> User | None:
    """Оппонент из reply или упоминания: get_chat → DB → get_chat_member."""
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
                uid = getattr(chat, "id", None)
                if uid:
                    try:
                        member = await bot.get_chat_member(message.chat.id, uid)
                        if member.user and not member.user.is_bot:
                            return member.user
                    except Exception:
                        from aiogram.types import User as TgUser

                        return TgUser(
                            id=uid,
                            is_bot=False,
                            first_name=getattr(chat, "first_name", None) or username,
                            username=getattr(chat, "username", None) or username,
                        )
            except Exception:
                logger.info("get_chat(@%s) failed, fallback to DB", username)

            try:
                uid = await _lookup_username_in_db(message.chat.id, username)
                if uid:
                    member = await bot.get_chat_member(message.chat.id, uid)
                    if member.user and not member.user.is_bot:
                        return member.user
            except Exception:
                logger.info("DB/@%s resolve failed", username, exc_info=True)
    return None


async def _duel_start_kb(bot: Bot, chat_id: int, room_id: str) -> InlineKeyboardMarkup:
    """URL-кнопка t.me/.../start=... (короткий alphanumeric + encode=True)."""
    from utils.deeplink import create_dm_start_link

    link = await create_dm_start_link(
        bot,
        request_func="minigame_ttt",
        chat_id=chat_id,
        room_id=room_id,
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⚔️ Start — открыть дуэль", url=link)]]
    )


async def _send_duel_links(
    bot: Bot,
    chat_id: int,
    creator_id: int,
    opponent_id: int,
    room_id: str,
    *,
    group_message: Message | None = None,
) -> None:
    """Опциональные ЛС с WebApp. Группа уже имеет Start — Forbidden не критичен."""
    url = _webapp_ttt_url(chat_id, room_id, opponent_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Открыть дуэль", web_app=WebAppInfo(url=url))]
        ]
    )
    failed: list[int] = []
    for uid, dm_text in (
        (creator_id, "⚔️ Дуэль создана! Откройте игру (вы — крестики):"),
        (opponent_id, "⚔️ Вас вызвали на дуэль! Откройте игру (вы — нолики):"),
    ):
        try:
            await bot.send_message(uid, dm_text, reply_markup=kb)
        except Exception as e:
            failed.append(uid)
            logger.warning("DM дуэль user=%s недоступен: %s", uid, e)

    if failed and group_message is not None:
        start_kb = await _duel_start_kb(bot, chat_id, room_id)
        names = ", ".join(f'<a href="tg://user?id={u}">игрок</a>' for u in failed)
        try:
            await group_message.answer(
                f"⚠️ {names}: бот не может написать в ЛС "
                f"(заблокирован или ещё не нажат /start). "
                f"Нажмите Start ниже:",
                reply_markup=start_kb,
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("не удалось уведомить группу о blocked DM")


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


@router.callback_query(F.data.startswith("mg:ttt:force_cancel:"))
async def on_ttt_force_cancel(callback: CallbackQuery):
    """Завершить sticky-комнату: только initiator или target этой room."""
    try:
        from shared.enums import GameRoomStatus

        room_id = callback.data.split(":")[-1]
        room = await GameRoomOrm.get(room_id)
        if room is None:
            await callback.answer("Комната не найдена", show_alert=True)
            return
        uid = callback.from_user.id
        if uid not in (room.initiator_id, room.target_id):
            await callback.answer("Завершить может только участник этой дуэли", show_alert=True)
            return
        await GameRoomOrm.update(str(room.id), status=GameRoomStatus.CANCELLED)
        try:
            get_redis().delete(_room_key(int(room.chat_id)))
            get_redis().delete(_picking_key(int(room.chat_id)))
        except Exception:
            pass
        if callback.message:
            try:
                await callback.message.edit_text("Дуэль завершена участником.")
            except Exception:
                pass
        await callback.answer("Дуэль завершена")
    except Exception:
        logger.exception("Ошибка force_cancel TTT")
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

        await _send_duel_links(
            callback.bot, chat_id, creator_id, user_id, str(room.id), group_message=callback.message
        )
        if callback.message:
            start_kb = await _duel_start_kb(callback.bot, chat_id, str(room.id))
            await callback.message.edit_text(
                "⚔️ Дуэль началась! Войти могут только участники — нажмите Start:",
                reply_markup=start_kb,
            )
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

    try:
        await GameRoomOrm.expire_overdue()
    except Exception:
        logger.exception("expire_overdue before TTT create")

    for uid in (creator_id, opponent.id):
        existing = await GameRoomOrm.get_active_for_user(uid)
        if existing:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Завершить дуэль",
                            callback_data=f"mg:ttt:force_cancel:{existing.id}",
                        )
                    ]
                ]
            )
            await message.reply(
                "У вас уже есть активная игра. Можете завершить её кнопкой ниже "
                "(доступно создателю и оппоненту той комнаты).",
                reply_markup=kb,
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
    start_kb = await _duel_start_kb(bot, message.chat.id, str(room.id))
    await message.answer(
        f"⚔️ Дуэль создана: вы против {mention_opp}.\n"
        "В комнату могут войти только вы двое. Нажмите Start:",
        reply_markup=start_kb,
        parse_mode="HTML",
    )
    await _send_duel_links(
        bot, message.chat.id, creator_id, opponent.id, str(room.id), group_message=message
    )
