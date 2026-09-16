import logging
from urllib.parse import parse_qs

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
            params = parse_qs(command.args)
            # Compact: c=<chat_id>&f=<ttt|roulette|slots>
            # Legacy: chat_id=...&request_func=minigame_...
            chat_id = params.get("c", params.get("chat_id", [None]))[0]
            short = params.get("f", [None])[0]
            request_func = params.get("request_func", [None])[0]
            if short and not request_func:
                request_func = {
                    "ttt": "minigame_ttt",
                    "roulette": "minigame_roulette",
                    "slots": "minigame_slots",
                    "profile": "profile",
                    "casino": "casino",
                    "ad": "advertise",
                    "advertise": "advertise",
                    "admin": "admin",
                }.get(short, short if short.startswith("minigame_") else f"minigame_{short}")

            match request_func, chat_id:
                case "profile", chat_id:
                    answer = await func.profile_for_chat(message.from_user.id, int(chat_id))
                    await message.answer(answer)
                case "casino", _:
                    await message.answer("Казино", reply_markup=build_inline_kb_webapp_casino())
                case "advertise", _:
                    from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_advertise
                    await message.answer("Реклама", reply_markup=build_inline_kb_webapp_advertise())
                case "admin", _:
                    if message.from_user.id not in _settings.ADMIN_ID_SET:
                        await message.answer("Только для администраторов")
                    else:
                        await message.answer("Админ-панель", reply_markup=build_inline_kb_webapp_admin())
                case "minigame_ttt", chat_id:
                    url = f"{_settings.WEBAPP_BASE_URL}/webapp/?page=ttt&chat_id={chat_id}"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Играть в крестики-нолики", web_app=WebAppInfo(url=url))]])
                    await message.answer("Крестики-нолики: откройте WebApp", reply_markup=kb)
                case "minigame_roulette", chat_id:
                    url = f"{_settings.WEBAPP_BASE_URL}/webapp/?page=roulette&chat_id={chat_id}"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎰 Играть в рулетку", web_app=WebAppInfo(url=url))]])
                    await message.answer("Рулетка: откройте WebApp", reply_markup=kb)
                case "minigame_slots", chat_id:
                    url = f"{_settings.WEBAPP_BASE_URL}/webapp/?page=slots&chat_id={chat_id}"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔔 Слот-машина", web_app=WebAppInfo(url=url))]])
                    await message.answer("Слот-машина: откройте WebApp", reply_markup=kb)
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
