import logging
import random
from datetime import datetime

from aiogram import Bot, F, Router, html
from aiogram.filters import Command
from aiogram.methods import SendAnimation, SendMessage
from aiogram.types import Message

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


def _tag_prefix(sub_tag: str) -> str:
    return f"[{sub_tag}] " if sub_tag else ""


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
    group_user: GroupUserOrm = await func.get_group_user(message)
    chat_id = message.chat.id

    match arr_msg:
        case []:
            messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
            answer = generate_text(messages)
            command = SendMessage(chat_id=chat_id, text=_tag_prefix(sub_tag) + answer)
        case ("включи" | "выключи") as enable, "ии":
            enable = enable == "включи"
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                await TelegramChatOrm.change_ai_generate_text(chat_settings.chat_id, enable)
                answer = "Включил ии" if enable else "Выключил ии"
            else:
                answer = "Эта команда доступна только для администраторов"
            command = SendMessage(chat_id=chat_id, text=answer)
        case "шанс", *chance:
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                if chance:
                    answer = await func.set_chance(message, chance[0])
                else:
                    answer, chance_val = await func.get_chance(message)
                try:
                    get_redis().set(f"tg_chat_chance:{message.chat.id}", chance_val, ex=120)
                except Exception:
                    pass
            else:
                answer = "Эта команда доступна только для администраторов"
            command = SendMessage(chat_id=chat_id, text=answer)
        case "ответь", *words:
            animation, answer = await func.yesno()
            gif = bool(words) and words[0] == "гиф"
            if gif:
                command = SendAnimation(chat_id=chat_id, animation=animation, caption=answer)
            else:
                command = SendMessage(chat_id=chat_id, text=answer)
        case "выбери", *words:
            answer = func.choice_words(words)
            command = SendMessage(chat_id=chat_id, text=answer)
        case ("работа" | "работать",):
            answer = await func.work(message, sub_tier)
            command = SendMessage(chat_id=chat_id, text=answer)
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
            command = SendMessage(chat_id=chat_id, text=answer)
        case "кто" | "кого", *words:
            members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(message.chat.id)
            if members:
                random_member = random.choice(members)
                answer = f"Я думаю {await random_member.mention_link_html()} " + " ".join(words)
            else:
                answer = "В чате нет участников"
            command = SendMessage(chat_id=chat_id, text=answer)
        case "кот", *text:
            command = CommandCat(chat_id=chat_id, text=text)
        case "кража", *_:
            answer = await func.rob(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer)
        case "перевод", *text:
            answer = await func.transfer(message, bot, text)
            command = SendMessage(chat_id=chat_id, text=answer)
        case "убить", *_:
            answer = await func.kill(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer)
        case "топ", *_:
            answer = await func.get_top_users_money(message)
            command = SendMessage(chat_id=chat_id, text=answer)
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
            command = SendMessage(chat_id=chat_id, text=answer)
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
    keyboard = build_inline_kb_subscribe()
    await message.answer("Выберите уровень подписки:", reply_markup=keyboard)


@router.message(Command("donate"))
async def donate_cmd(message: Message):
    keyboard = build_inline_kb_donate()
    await message.answer("💰 Поддержать проект Bot Vasya:", reply_markup=keyboard)


@router.message(Command("advertise"))
async def advertise_cmd(message: Message):
    keyboard = build_inline_kb_webapp_advertise()
    await message.answer("📢 Подача рекламы. Откройте форму:", reply_markup=keyboard)


@router.message(Command("admin_panel"))
async def admin_panel_cmd(message: Message):
    if message.from_user.id not in _settings.ADMIN_ID_SET:
        await message.answer("Эта команда доступна только администраторам")
        return
    keyboard = build_inline_kb_webapp_admin()
    await message.answer("🛠 Админ-панель:", reply_markup=keyboard)


@router.message(Command("casino"))
async def casino(message: Message):
    from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_casino

    keyboard = build_inline_kb_webapp_casino()
    await message.answer("Вход в казино", reply_markup=keyboard)


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
        if chat_settings.ai_generate_text:
            messages = [{"role": "user", "content": f"[{msg[1] or msg[2] or msg[3]}] " + msg[0]} for msg in reversed(msg_from_db)]
            answer = await generate_text_from_ai(messages + messages_rules)
        else:
            messages = [msg[0] for msg in msg_from_db]
            answer = generate_text(messages)
        await message.answer(answer)
