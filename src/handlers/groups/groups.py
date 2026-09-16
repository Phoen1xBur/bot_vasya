import logging
import random
from datetime import datetime

from aiogram import Bot, F, Router, html
from aiogram.filters import Command
from aiogram.methods import SendAnimation, SendMessage
from aiogram.types import InlineKeyboardMarkup, Message

from shared.config import get_settings
from shared.enums import SubscriptionTier
from shared.bot_identity import is_bot_user
from shared.models import GroupUserOrm, MessageOrm, TelegramChatOrm
from shared.redis_client import get_redis
from keyboards.inline_kb_minigames import build_inline_kb_minigames_select
from keyboards.inline_kb_profile_change_settings import profile_change_settings
from keyboards.inline_kb_webapp_casino import (
    build_inline_kb_webapp_admin,
    build_inline_kb_webapp_advertise,
    build_inline_kb_webapp_profile,
)
from keyboards.inline_kb_subscribe_donate import build_inline_kb_donate, build_inline_kb_subscribe
from utils.auto_delete_message_service import AutoDeleteService
from utils.filters import BotNameFilter, ChatTypeFilter, MessageTypeFilter
from utils.utils import generate_text, generate_text_from_ai
from shared.enums import ChatType, ContentType
from handlers import func
from handlers.command import CommandCat

router = Router(name=__name__)
logger = logging.getLogger(__name__)
router.message.filter(
    ChatTypeFilter(ChatType.GROUP, ChatType.SUPERGROUP),
    MessageTypeFilter(ContentType.TEXT),
)

_settings = get_settings()

messages_rules = [
    {
        "role": "system",
        "content": (
            "Ты являешься ботом Васей. Состоишь в чате со множеством людей. Они могут общаться между собой так и с тобой. "
            "Постарайся отличать такие сообщения, и не отвечать на то, что тебя не касается. "
            "По возможности отвечай только на последние 1-2 сообщения. "
            "В квадратных скобках в начале сообщения отображается имя/ник пользователя. "
            "Сам ответ не давай с именем в квадратных скобках."
        ),
    },
    {
        "role": "system",
        "content": (
            "Старайся отвечать коротко, по делу. Ориентируйся на текущую дату: "
            f"{datetime.now().date()}. Учитывай Московское время."
        ),
    },
]



async def _dm_deeplink_button(bot: Bot, text: str, request_func: str, chat_id: int | None = None) -> InlineKeyboardMarkup:
    from urllib.parse import urlencode
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from aiogram.utils.deep_linking import create_start_link
    q = {"request_func": request_func}
    if chat_id is not None:
        q["chat_id"] = chat_id
    link = await create_start_link(bot, urlencode(q), encode=True)
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=link)]])

def _tag_prefix(sub_tag: str) -> str:
    return f"[{sub_tag}] " if sub_tag else ""


def _enough_context(messages) -> bool:
    """Не отвечаем, пока в чате мало сохранённых сообщений."""
    need = int(getattr(_settings, "MIN_AI_CONTEXT_MESSAGES", 30) or 30)
    n = len(messages) if messages is not None else 0
    if n < need:
        logger.info(
            "skip reply: low context chat messages=%s need=%s",
            n,
            need,
        )
        return False
    return True


@router.message(BotNameFilter(bot_names=_settings.BOT_NAMES), (F.text[0] != "/"))
async def answer_by_bot_name(
    message: Message,
    bot: Bot,
    message_delete_service: AutoDeleteService,
    chat_settings: TelegramChatOrm | None,
    sub_tier: SubscriptionTier = SubscriptionTier.FREE,
    sub_tag: str = "",
):
    if chat_settings is None:
        chat_settings = await TelegramChatOrm.get_telegram_chat(message.chat.id)
        if chat_settings is None:
            await TelegramChatOrm.insert_or_update_telegram_chat(chat_id=message.chat.id)
            chat_settings = await TelegramChatOrm.get_telegram_chat(message.chat.id)
        if chat_settings is None:
            return

    arr_msg = [w.casefold() for w in message.text.split()[1:]]
    try:
        group_user: GroupUserOrm = await func.get_group_user(message)
    except Exception:
        logger.exception("get_group_user failed for name-cmd chat=%s", message.chat.id)
        await message.answer("Не удалось загрузить профиль участника. Попробуйте ещё раз.")
        return
    chat_id = message.chat.id

    match arr_msg:
        case []:
            msg_from_db = await MessageOrm.get_messages(message.chat.id)
            if not _enough_context(msg_from_db):
                return
            messages = [msg[0] for msg in msg_from_db]
            answer = generate_text(messages)
            command = SendMessage(chat_id=chat_id, text=_tag_prefix(sub_tag) + answer, parse_mode="HTML")
        case ("включи" | "выключи") as enable, "ии":
            enable = enable == "включи"
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                await TelegramChatOrm.change_ai_generate_text(chat_settings.chat_id, enable)
                answer = "Включил ии" if enable else "Выключил ии"
            else:
                answer = "Эта команда доступна только для администраторов"
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "шанс", *chance:
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                if chance:
                    answer = await func.set_chance(message, chance[0])
                    try:
                        chance_val = int(chance[0])
                    except (TypeError, ValueError):
                        chance_val = None
                    if chance_val is not None and 0 <= chance_val <= 100:
                        try:
                            get_redis().set(f"tg_chat_chance:{message.chat.id}", chance_val, ex=120)
                        except Exception:
                            pass
                else:
                    answer, chance_val = await func.get_chance(message)
                    try:
                        get_redis().set(f"tg_chat_chance:{message.chat.id}", chance_val, ex=120)
                    except Exception:
                        pass
            else:
                answer = "⛔ Команда «шанс» доступна только администраторам чата"
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "ответь", *words:
            animation, answer = await func.yesno()
            gif = bool(words) and words[0] == "гиф"
            if gif:
                command = SendAnimation(chat_id=chat_id, animation=animation, caption=answer)
            else:
                command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "выбери", *words:
            answer = func.choice_words(words)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case ("работа" | "работать",):
            answer = await func.work(message, sub_tier)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "профиль", *_:
            answer, _user = await func.profile(message)
            notification = "❌ Выключить" if _user and _user.can_tag else "✅ Включить"
            msg_answer = await message.answer(
                answer,
                reply_markup=await profile_change_settings(
                    message.from_user.id, message.chat.id, notification
                ),
            )
            message_delete_service.schedule(message.chat.id, message.message_id)
            message_delete_service.schedule(msg_answer.chat.id, msg_answer.message_id)
            return
        case "вероятность", *words:
            text = " ".join(words)
            answer = f"Вероятность {text}: {random.randint(0, 100)}%"
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "кто" | "кого", *words:
            members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(message.chat.id)
            if members:
                random_member = random.choice(members)
                answer = f"Я думаю {await random_member.mention_link_html()} " + " ".join(words)
            else:
                answer = "В чате нет участников"
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "кот", *text:
            command = CommandCat(chat_id=chat_id, text=text)
        case "кража", *_:
            answer = await func.rob(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "перевод", *text:
            answer = await func.transfer(message, bot, text)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "убить", *_:
            answer = await func.kill(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case "топ", *_:
            answer = await func.get_top_users_money(message)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
        case ("minigames" | "миниигры" | "игры", *_):
            try:
                get_redis().hset(f"mg:lobby:{chat_id}", mapping={"creator_id": message.from_user.id})
            except Exception:
                pass
            keyboard = build_inline_kb_minigames_select()
            command = SendMessage(chat_id=chat_id, text="Выберите мини-игру:", reply_markup=keyboard)
        case _:
            logger.info(
                "groups name-cmd unmatched: chat=%s text=%r arr=%r",
                chat_id,
                message.text,
                arr_msg,
            )
            msg_from_db = await MessageOrm.get_messages(message.chat.id)
            if chat_settings.ai_generate_text:
                messages = [{"role": "user", "content": f"[{msg[1] or msg[2] or msg[3]}] " + msg[0]} for msg in reversed(msg_from_db)]
                messages.append({"role": "user", "content": message.text})
                answer = await generate_text_from_ai(messages + messages_rules)
                answer = _tag_prefix(sub_tag) + answer
            else:
                messages = [msg[0] for msg in msg_from_db]
                messages.append(message.text)
                answer = _tag_prefix(sub_tag) + generate_text(messages)
            command = SendMessage(chat_id=chat_id, text=answer, parse_mode="HTML")
    if command:
        await bot(command)


@router.message(Command("profile"))
async def profile(message: Message, message_delete_service: AutoDeleteService):
    answer, user_orm = await func.profile(message)
    notification = "❌ Выключить" if user_orm and user_orm.can_tag else "✅ Включить"
    msg_answer = await message.answer(
        answer,
        reply_markup=await profile_change_settings(message.from_user.id, message.chat.id, notification),
    )
    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(msg_answer.chat.id, msg_answer.message_id)


@router.message(Command("top_users"))
async def top_users(message: Message, message_delete_service: AutoDeleteService):
    answer = await func.get_top_users_money(message)
    msg_answer = await message.answer(answer)
    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(msg_answer.chat.id, msg_answer.message_id)


@router.message(Command("minigames"))
async def minigames(message: Message):
    try:
        get_redis().hset(f"mg:lobby:{message.chat.id}", mapping={"creator_id": message.from_user.id})
    except Exception:
        pass
    keyboard = build_inline_kb_minigames_select()
    await message.answer("Выберите мини-игру:", reply_markup=keyboard)


@router.message(Command("work"))
async def work(message: Message, message_delete_service: AutoDeleteService, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    answer = await func.work(message, sub_tier)
    msg_answer = await message.answer(answer)
    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(msg_answer.chat.id, msg_answer.message_id)


@router.message(Command("free"))
async def free_cmd(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    answer = await func.free_from_prison(message, sub_tier)
    await message.answer(answer)


@router.message(Command("subscribe"))
async def subscribe_cmd(message: Message):
    kb = await _dm_deeplink_button(message.bot, "⭐ Оформить подписку в ЛС", "subscribe")
    await message.answer(
        "⭐ Подписка оформляется в личке с ботом (Mini App).\n"
        "Нажмите кнопку ниже:",
        reply_markup=kb,
    )


@router.message(Command("donate"))
async def donate_cmd(message: Message):
    kb = await _dm_deeplink_button(message.bot, "💰 Донат в ЛС", "donate")
    await message.answer("💰 Поддержать проект — откройте Mini App в личке:", reply_markup=kb)


@router.message(Command("advertise"))
async def advertise_cmd(message: Message):
    kb = await _dm_deeplink_button(message.bot, "📢 Реклама в ЛС", "advertise")
    await message.answer("📢 Подача рекламы доступна в личке с ботом:", reply_markup=kb)


@router.message(Command("admin_panel"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id not in _settings.ADMIN_ID_SET:
        await message.answer("Эта команда доступна только администраторам")
        return
    keyboard = build_inline_kb_webapp_admin()
    await message.answer("🛠 Админ-панель:", reply_markup=keyboard)


@router.message(Command("ai_generate"))
async def ai_generate_cmd(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    from shared.ai import ai_generate_text, check_ai_limit, increment_ai_usage
    prompt = (message.text or "").replace("/ai_generate", "").strip()
    if not prompt:
        await message.answer("Напишите запрос: /ai_generate <тема>")
        return
    if sub_tier == SubscriptionTier.FREE:
        await message.answer("AI-команды доступны по подписке. /subscribe")
        return
    if not await check_ai_limit(message.from_user.id, sub_tier):
        await message.answer("Дневной лимит AI-запросов исчерпан.")
        return
    await message.answer("⏳ Генерирую...")
    try:
        result = await ai_generate_text(message.from_user.id, prompt)
        await increment_ai_usage(message.from_user.id)
        await message.answer(result)
    except Exception:
        logger.exception("ai_generate failed")
        await message.answer("Ошибка AI-генерации. Попробуйте позже.")


@router.message(Command("ai_roleplay"))
async def ai_roleplay_cmd(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE):
    from shared.ai import ai_roleplay, check_ai_limit, increment_ai_usage
    prompt = (message.text or "").replace("/ai_roleplay", "").strip()
    if not prompt:
        await message.answer("Напишите сценарий: /ai_roleplay <описание>")
        return
    if sub_tier == SubscriptionTier.FREE:
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
        logger.exception("ai_roleplay failed")
        await message.answer("Ошибка AI. Попробуйте позже.")


@router.message(Command("casino"))
async def casino(message: Message):
    kb = await _dm_deeplink_button(message.bot, "🎰 Казино в ЛС", "casino", chat_id=message.chat.id)
    await message.answer("🎰 Казино открывается в личке с ботом:", reply_markup=kb)


@router.message(F.text[0] != "/")
async def echo(message: Message, chat_settings: TelegramChatOrm | None):
    if message.text is None:
        return
    if message.via_bot or message.forward_origin:
        return

    if chat_settings is None:
        chat_settings = await TelegramChatOrm.get_telegram_chat(message.chat.id)
        if chat_settings is None:
            await TelegramChatOrm.insert_or_update_telegram_chat(chat_id=message.chat.id)
            chat_settings = await TelegramChatOrm.get_telegram_chat(message.chat.id)
        if chat_settings is None:
            return

    group_user: GroupUserOrm = await func.get_group_user(message)
    await MessageOrm.insert_message(group_user.id, message.text.replace("@", ""))

    if message.reply_to_message and is_bot_user(
        message.reply_to_message.from_user.id,
        getattr(message.reply_to_message.from_user, "username", None),
    ):
        msg_from_db = await MessageOrm.get_messages(message.chat.id)
        if not _enough_context(msg_from_db):
            return
        if chat_settings.ai_generate_text:
            messages = [{"role": "user", "content": f"[{msg[1] or msg[2] or msg[3]}] " + msg[0]} for msg in reversed(msg_from_db)]
            messages.insert(-1, {"role": "assistant", "content": message.reply_to_message.text})
            answer = await generate_text_from_ai(messages + messages_rules)
        else:
            messages = [msg[0] for msg in msg_from_db]
            answer = generate_text(messages)
        await message.answer(answer)
        return

    try:
        chance = get_redis().get(f"tg_chat_chance:{message.chat.id}")
    except Exception:
        chance = None
    if chance is None:
        chance_row = await TelegramChatOrm.get_chance(message.chat.id)
        chance = chance_row.answer_chance if chance_row else chat_settings.answer_chance
        try:
            get_redis().set(f"tg_chat_chance:{message.chat.id}", chance, ex=120)
        except Exception:
            pass
    if random.randint(1, 100) <= int(chance):
        msg_from_db = await MessageOrm.get_messages(message.chat.id)
        if not _enough_context(msg_from_db):
            return
        if chat_settings.ai_generate_text:
            messages = [{"role": "user", "content": f"[{msg[1] or msg[2] or msg[3]}] " + msg[0]} for msg in reversed(msg_from_db)]
            answer = await generate_text_from_ai(messages + messages_rules)
        else:
            messages = [msg[0] for msg in msg_from_db]
            answer = generate_text(messages)
        await message.answer(answer)
