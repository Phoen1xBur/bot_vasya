import logging
from utils.deeplink import parse_start_args, resolve_room_id

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_admin, build_inline_kb_webapp_casino
from shared.config import get_settings
from shared.enums import SubscriptionTier
from utils.filters import ChatTypeFilter
from shared.enums import ChatType
from . import func
from .command import CommandStart as MyCommandStart
from shared.ai import (
    ai_generate_text,
    ai_roleplay,
    check_ai_limit,
    get_user_tier,
    increment_ai_usage,
)

logger = logging.getLogger(__name__)
router = Router(name=__name__)
router.message.filter(ChatTypeFilter(ChatType.PRIVATE))
_settings = get_settings()


@router.message(CommandStart(deep_link=True, deep_link_encoded=True))
async def start(message: Message, command: CommandObject, bot: Bot):
    if command.args:
        try:
            params = parse_start_args(command.args)
            chat_id = params.get("chat_id")
            request_func = params.get("request_func")

            room = await resolve_room_id(params.get("room"))
            match request_func, chat_id:
                case "profile", chat_id:
                    answer = await func.profile_for_chat(message.from_user.id, int(chat_id))
                    await message.answer(answer)
                case "casino", chat_id:
                    cid = int(chat_id) if chat_id else None
                    await message.answer("🎰 Казино открыто в Mini App:", reply_markup=build_inline_kb_webapp_casino(cid))
                case "subscribe", _:
                    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=subscribe"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Оформить подписку", web_app=WebAppInfo(url=url))]])
                    await message.answer("Выберите тариф в Mini App — оплата прямо там:", reply_markup=kb)
                case "donate", _:
                    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=subscribe&tab=donate"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 Поддержать проект", web_app=WebAppInfo(url=url))]])
                    await message.answer("Донат через Mini App:", reply_markup=kb)
                case "advertise", _:
                    from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_advertise
                    await message.answer("📢 Форма рекламы:", reply_markup=build_inline_kb_webapp_advertise())
                case "minigame_ttt", chat_id:
                    # Дуэль: только initiator/target комнаты получают WebApp-кнопку
                    if room:
                        from shared.models.game_room import GameRoomOrm
                        gr = await GameRoomOrm.get(room)
                        uid = message.from_user.id if message.from_user else None
                        if gr is None:
                            await message.answer("Комната не найдена или истекла.")
                            return
                        if uid not in (gr.initiator_id, gr.target_id):
                            await message.answer("Эта комната не для вас.")
                            return
                        q = f"page=ttt&chat_id={chat_id or gr.chat_id}&room={room}"
                        if gr.target_id:
                            q += f"&target={gr.target_id}"
                        url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?{q}"
                        role = "крестики (X)" if uid == gr.initiator_id else "нолики (O)"
                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="⚔️ Открыть дуэль", web_app=WebAppInfo(url=url))]]
                        )
                        await message.answer(f"⚔️ Дуэль — вы {role}. Откройте Mini App:", reply_markup=kb)
                    else:
                        await message.answer(
                            "Ссылка на дуэль устарела. Создайте новую игру командой мини-игр в группе."
                        )
                case "minigame_roulette", chat_id:
                    q = f"page=roulette&chat_id={chat_id}"
                    if room:
                        q += f"&room={room}"
                    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?{q}"
                    short = (room or "").replace("-", "")[:8]
                    caption = "🎰 Рулетка — откройте Mini App:"
                    if short:
                        caption = (
                            f"🎰 Рулетка · комната <code>{short}</code>\n"
                            "Откройте Mini App:"
                        )
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰 Открыть рулетку", web_app=WebAppInfo(url=url))]])
                    await message.answer(caption, reply_markup=kb, parse_mode="HTML")
                case "minigame_slots", chat_id:
                    url = f"{_settings.WEBAPP_BASE_URL}/webapp/?page=slots&chat_id={chat_id}"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔔 Слот-машина", web_app=WebAppInfo(url=url))]])
                    await message.answer("Слот-машина — откройте Mini App:", reply_markup=kb)
                case _:
                    await message.answer(f"Неизвестная команда: {request_func}")
        except Exception:
            await message.answer("Ошибка обработки параметров запуска")
            logger.exception("Ошибка deep-link")
    else:
        await bot(MyCommandStart(chat_id=message.chat.id))


@router.message(Command("admin_panel"))
async def admin_panel(message: Message):
    if message.from_user.id not in _settings.ADMIN_ID_SET:
        await message.answer("Эта команда доступна только администраторам")
        return
    await message.answer("🛠 Админ-панель:", reply_markup=build_inline_kb_webapp_admin())


@router.message(Command("ai_generate"))
async def ai_generate_cmd(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    """AI-генерация текста (только для подписчиков)."""
    prompt = (message.text or "").replace("/ai_generate", "").strip()
    if not prompt:
        await message.answer("Напишите запрос после команды: /ai_generate <тема>")
        return
    tier = sub_tier
    if tier == SubscriptionTier.FREE:
        await message.answer("AI-команды доступны по подписке. /subscribe")
        return
    if not await check_ai_limit(message.from_user.id, tier):
        await message.answer("Дневной лимит AI-запросов исчерпан. /subscribe для увеличения.")
        return
    await message.answer("⏳ Генерирую...")
    try:
        result = await ai_generate_text(message.from_user.id, prompt)
        await increment_ai_usage(message.from_user.id)
        await message.answer(result)
    except Exception:
        await message.answer("Ошибка AI-генерации. Попробуйте позже.")


@router.message(Command("ai_roleplay"))
async def ai_roleplay_cmd(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    """Ролевая игра с AI (только для подписчиков)."""
    prompt = (message.text or "").replace("/ai_roleplay", "").strip()
    if not prompt:
        await message.answer("Напишите сценарий: /ai_roleplay <описание>")
        return
    if tier_free := sub_tier == SubscriptionTier.FREE:
        await message.answer("AI-команды доступны по подписке. /subscribe")
        return
    if not await check_ai_limit(message.from_user.id, sub_tier):
        await message.answer("Дневной лимит AI-запросов исчерпан.")
        return
    await message.answer("⏳ Играю...")
    try:
        result = await ai_roleplay(message.from_user.id, prompt)
        await increment_ai_usage(message.from_user.id)
        await message.answer(result)
    except Exception:
        await message.answer("Ошибка AI. Попробуйте позже.")


@router.message(Command("subscribe"))
async def subscribe_cmd(message: Message):
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=subscribe"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⭐ Подписка в Mini App", web_app=WebAppInfo(url=url))]]
    )
    await message.answer(
        "⭐ <b>Подписка VIP / Premium / Elite</b>\n"
        "Оплата в Mini App — после оплаты статус появится в профиле автоматически.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(Command("donate"))
async def donate_cmd(message: Message):
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=subscribe&tab=donate"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💰 Донат в Mini App", web_app=WebAppInfo(url=url))]]
    )
    await message.answer(
        "💰 Поддержать проект Bot Vasya через Mini App:",
        reply_markup=kb,
    )


@router.message(Command("advertise"))
async def advertise_cmd(message: Message):
    from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_advertise
    await message.answer("📢 Подача рекламы. Откройте форму:", reply_markup=build_inline_kb_webapp_advertise())


@router.message(Command("casino"))
async def casino_cmd(message: Message):
    await message.answer("Вход в казино", reply_markup=build_inline_kb_webapp_casino())


@router.message(Command("profile"))
async def profile_cmd(message: Message):
    from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_profile
    # В личке нет group chat — открываем WebApp профиль без chat_id
    url = f"{_settings.WEBAPP_BASE_URL.rstrip('/')}/webapp/?page=profile"
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👤 Профиль", web_app=WebAppInfo(url=url))]]
    )
    await message.answer("Ваш профиль:", reply_markup=kb)


@router.message(Command("unsubscribe"))
async def unsubscribe_cmd(message: Message):
    try:
        from shared.models.subscription import SubscriptionOrm
        ok = await SubscriptionOrm.cancel_auto_renew(message.from_user.id)
        if ok:
            await message.answer("Автопродление отключено.")
        else:
            await message.answer("Активная подписка не найдена.")
    except Exception:
        logger.exception("unsubscribe failed")
        await message.answer("Не удалось отключить автопродление. Попробуйте позже.")

