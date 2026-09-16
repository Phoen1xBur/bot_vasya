import asyncio
from datetime import datetime as dt, timedelta as td
import logging
import random
from typing import Any

import aiogram
import aiohttp
import pyrogram.errors
from pyrogram.enums import ChatMemberStatus
from aiogram.types import Message, ChatMemberUpdated, User as AiogramUser
from aiogram.methods import GetChatMember
from aiogram import html

from shared.enums import TransactionType, RandomRob, SubscriptionTier
from shared.economy import (
    PRISON_TIME,
    ROB_COOLDOWN,
    ROB_PENALTY,
    ROB_VICTIM_MIN_MONEY,
    WORK_COOLDOWN,
    apply_work_bonus,
    roll_rob_amount,
    roll_rob_outcome,
    roll_work_income,
)
from shared.models import (
    GroupUserOrm,
    ProfessionOrm,
    TelegramChatOrm,
    TransactionOrm,
    UserOrm,
)
from shared.models.money import Prison
from shared.models.subscription import TIER_WORK_BONUS
from shared.utils import declension_word_by_number
from utils.utils import generate_text, generate_text_from_ai

# Импорт pyrogram-клиента (создан в run_bot)
from run_bot import app  # noqa: F401

logger = logging.getLogger(__name__)

_pyrogram_lock = asyncio.Lock()


async def ensure_pyrogram() -> None:
    """Keep one long-lived Pyrogram session (avoid sqlite closed database)."""
    async with _pyrogram_lock:
        if not app.is_connected:
            await app.start()



MEMBER_TYPE_ADMIN = (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)



async def ensure_group_user_from_message(message: Message) -> GroupUserOrm:
    """Создать/обновить User + GroupUser из aiogram Message без Pyrogram."""
    tg_user = message.from_user
    if tg_user is None:
        raise ValueError("message.from_user is required")
    await TelegramChatOrm.insert_or_update_telegram_chat(message.chat.id)
    await UserOrm.insert_or_update_user(tg_user.id, tg_user)
    await GroupUserOrm.insert_or_update_group_user(
        tg_user.id, message.chat.id, chat_member_status=ChatMemberStatus.MEMBER
    )
    group_user = await GroupUserOrm.get_group_user(tg_user.id, message.chat.id)
    if group_user is None:
        raise RuntimeError(f"Failed to upsert GroupUser user={tg_user.id} chat={message.chat.id}")
    return group_user


async def get_group_user(message: Message) -> GroupUserOrm:
    """Вернуть GroupUser; при отсутствии — upsert из aiogram, Pyrogram не блокирует ответ."""
    group_user = await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    if group_user:
        return group_user

    group_user = await ensure_group_user_from_message(message)
    try:
        await update_users(message)
    except Exception:
        logger.warning(
            "update_users failed after upsert (chat=%s user=%s); continuing",
            message.chat.id,
            message.from_user.id,
            exc_info=True,
        )
    return await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id) or group_user


async def update_users(event: ChatMemberUpdated | Message) -> None:
    """Синхронизация участников чата с БД + обновление chat_unique_users."""
    await ensure_pyrogram()
    async for member in app.get_chat_members(event.chat.id):
        if member.user.is_bot:
            continue
        await UserOrm.insert_or_update_user(member.user.id, member.user)
        await GroupUserOrm.insert_or_update_group_user(
            member.user.id, event.chat.id, chat_member_status=member.status
        )
    # Обновляем кэш уникальных пользователей для таргетинга рекламы
    await _update_chat_unique_users(event.chat.id)


async def update_user(event: ChatMemberUpdated) -> None:
    await ensure_pyrogram()
    try:
        member = await app.get_chat_member(event.chat.id, event.new_chat_member.user.id)
    except pyrogram.errors.bad_request_400.UserNotParticipant:
        await GroupUserOrm.insert_or_update_group_user(
            event.new_chat_member.user.id, event.chat.id,
            chat_member_status=ChatMemberStatus.LEFT,
        )
        return
    if member.user.is_bot:
        return
    await UserOrm.insert_or_update_user(member.user.id, member.user)
    await GroupUserOrm.insert_or_update_group_user(member.user.id, event.chat.id, chat_member_status=member.status)
    await _update_chat_unique_users(event.chat.id)


async def _update_chat_unique_users(chat_id: int) -> None:
    """Обновить кэш уникальных пользователей чата (для таргетинга рекламы)."""
    try:
        members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(chat_id)
        user_ids = [m.user_id for m in members]
        from shared.models.ad_campaign import ChatUniqueUsersOrm

        await ChatUniqueUsersOrm.upsert(chat_id, user_ids)
    except Exception:
        logger.debug("Не удалось обновить chat_unique_users для %s", chat_id, exc_info=True)


async def get_user_by_username(chat_id: int, username: str) -> pyrogram.types.User | None:
    await ensure_pyrogram()
    try:
        member = await app.get_chat_member(chat_id, username)
        return member.user
    except pyrogram.errors.bad_request_400.UserNotParticipant:
        return None


async def set_chance(message: Message, chance: int) -> str:
    answer_error = "Шанс должен быть числом от 0 до 100"
    try:
        chance = int(chance)
    except (ValueError, TypeError):
        return answer_error
    if chance > 100 or chance < 0:
        return answer_error
    await TelegramChatOrm.change_answer_chance(message.chat.id, chance)
    return f"Шанс сообщения изменен на {chance}"


async def get_chance(message: Message) -> tuple[str, int]:
    chance_row = await TelegramChatOrm.get_chance(message.chat.id)
    chance = chance_row.answer_chance if chance_row else 5
    answer = (
        f"Шанс сообщения в группе {chance}%\n"
        f'Для изменения шанса напишите "Вася шанс [число шанса от 0 до 100]"'
    )
    return answer, chance


def choice_words(words) -> str:
    if not words:
        return "Нечего выбирать"
    words_lower = [t.lower() for t in words]
    count_or = words_lower.count("или")
    if count_or != 1:
        return "В предложении должен присутствовать один выбор посредством ИЛИ"
    if words_lower[0] == "или" or words_lower[-1] == "или":
        return "Выбор ИЛИ не должен находиться в начале или конце"
    index_or = words_lower.index("или")
    return " ".join(words[:index_or] if random.random() < 0.5 else words[index_or + 1:])


async def yesno() -> tuple[str, str]:
    url = "https://yesno.wtf/api"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            j = await response.json()
    animation, answer_en = j["image"], j["answer"]
    answers = {"yes": "Да", "no": "Нет", "maybe": "Может быть"}
    answer_ru = answers.get(answer_en, "Спроси позже...")
    return animation, answer_ru


def next_activity_from_seconds(next_activity_seconds: int) -> tuple[str, str]:
    delta = td(seconds=next_activity_seconds)
    next_activity_time = dt.now() + delta
    hours, minutes = next_activity_seconds // 3600, next_activity_seconds % 3600 // 60
    hours_str = declension_word_by_number(hours, "часов", "час", "часа")
    minutes_str = declension_word_by_number(minutes, "минут", "минута", "минуты")
    next_time = f"{hours} {hours_str} {minutes} {minutes_str}"
    at_time = next_activity_time.strftime("%Y-%m-%d в %H:%M:%S")
    return next_time, at_time


def next_activity(created_at: dt, after_time: td = WORK_COOLDOWN) -> tuple[bool, str, str]:
    delta = dt.now() - created_at
    can_activity = after_time < delta
    next_time = ""
    at_time = ""
    if not can_activity:
        next_work_seconds = (after_time - delta).seconds
        next_work_str = (dt.now() + (after_time - delta)).strftime("%Y-%m-%d в %H:%M:%S")
        hours, minutes = next_work_seconds // 3600, next_work_seconds % 3600 // 60
        hours_str = declension_word_by_number(hours, "часов", "час", "часа")
        minutes_str = declension_word_by_number(minutes, "минут", "минута", "минуты")
        next_time = f"{hours} {hours_str} {minutes} {minutes_str}"
        at_time = next_work_str
    return can_activity, next_time, at_time


async def work(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE) -> str:
    """Работа — стабильный доход. Бонус подписки только к работе."""
    group_user_from = await get_group_user(message)
    last_trans = await TransactionOrm.get_last_transaction_by_params(
        transaction_type=TransactionType.WORK, group_user_to_id=group_user_from.id
    )
    is_prisoner, prison_time = Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if is_prisoner:
        next_time, at_time = next_activity_from_seconds(prison_time)
        return (
            f"Вы не можете работать пока находитесь в тюрьме!\n"
            f"Следующая работа через {html.bold(next_time)}\n"
            f"{html.italic(at_time)} (GMT+3)"
        )
    if last_trans:
        can_work, next_time, at_time = next_activity(last_trans.created_at, WORK_COOLDOWN)
        if not can_work:
            return (
                f"Вы еще не отдохнули.\n"
                f"Следующая работа через {html.bold(next_time)}\n"
                f"{html.italic(at_time)} (GMT+3)"
            )

    profession: ProfessionOrm = random.choice(await ProfessionOrm.get_all_profession())
    base_income = roll_work_income()
    income, bonus = apply_work_bonus(base_income, sub_tier)
    vasya_coin = declension_word_by_number(income, "васякоинов", "васякоин", "васякоина")
    await group_user_from.money_plus(income)
    await TransactionOrm.insert_transaction(None, group_user_from.id, TransactionType.WORK, income)

    work_text = (
        f"{await group_user_from.mention_link_html()} устраивается на должность "
        f"{html.bold(html.italic(profession.name))} и зарабатывает {income} {vasya_coin}"
    )
    if bonus > 0:
        tag = {"vip": "[VIP]", "premium": "[Premium]", "elite": "[Elite]"}.get(sub_tier.value, "")
        work_text += f"\n{tag} Бонус подписки: +{int(bonus * 100)}% к заработку!"
    if profession.accompanying_text:
        work_text += f"\n\n{html.italic(profession.accompanying_text)}"
    return work_text


async def rob(message: Message, bot: aiogram.Bot) -> str:
    """Кража — высокий риск / высокий доход."""
    group_user_from = await get_group_user(message)
    last_trans = await TransactionOrm.get_last_transaction_by_params(
        transaction_type=TransactionType.ROB, group_user_to_id=group_user_from.id
    )
    is_prisoner, prison_time = Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if is_prisoner:
        next_time, at_time = next_activity_from_seconds(prison_time)
        return (
            f"Вы не можете красть пока находитесь в тюрьме!\n"
            f"Следующая кража через {html.bold(next_time)}\n"
            f"{html.italic(at_time)} (GMT+3)"
        )
    if last_trans:
        can_rob, next_time, at_time = next_activity(last_trans.created_at, ROB_COOLDOWN)
        if not can_rob:
            return (
                f"За вами пристально следят.\n"
                f"Следующая кража через {html.bold(next_time)}\n"
                f"{html.italic(at_time)} (GMT+3)"
            )

    victim_user_orm, victim_user_message = await get_user_by_message(message, bot)
    if victim_user_orm is None:
        return "Вы не выбрали кого обворовать!"
    if message.from_user.id == victim_user_message.id:
        return "Нельзя воровать у самого себя!"
    if victim_user_orm.money < ROB_VICTIM_MIN_MONEY:
        return "У этого пользователя недостаточно денег!"

    money = roll_rob_amount()
    vasya_coin = declension_word_by_number(money, "васякоинов", "васякоин", "васякоина")
    outcome = roll_rob_outcome()

    match outcome:
        case RandomRob.SUCCESS:
            await TransactionOrm.insert_transaction(
                victim_user_orm.id, group_user_from.id, TransactionType.ROB, money
            )
            await group_user_from.money_plus(money)
            await victim_user_orm.money_minus(money)
            return f"Вы украли у {await victim_user_orm.mention_link_html()} {money} {vasya_coin}"
        case RandomRob.FAIL:
            await TransactionOrm.insert_transaction(
                victim_user_orm.id, group_user_from.id, TransactionType.ROB, 0
            )
            return random.choice([
                f"Вы попытались украсть {money} {vasya_coin}, но попытка не удалась. Действуйте осторожнее!",
                f"Кража на сумму {money} {vasya_coin} провалилась! Жертва оказалась внимательнее.",
                f"Неудача! Не удалось украсть {money} {vasya_coin}.",
                f"Попытка украсть {money} {vasya_coin} была замечена. В следующий раз повезёт больше!",
            ])
        case RandomRob.POLICE:
            await TransactionOrm.insert_transaction(
                victim_user_orm.id, group_user_from.id, TransactionType.ROB, 0
            )
            Prison.add_prisoner(
                chat_id=message.chat.id, user_id=message.from_user.id, imprisonment_time=PRISON_TIME
            )
            await group_user_from.money_minus(ROB_PENALTY)
            return (
                f"При попытке украсть {money} {vasya_coin}, Вы попались полиции.\n"
                f"Вас отправили в тюрьму на {PRISON_TIME.seconds // 3600} часов.\n"
                f"{html.bold(html.italic(f'В качестве штрафа с вас взяли {ROB_PENALTY} васякоинов'))}"
            )
        case _:
            raise ValueError("Необработанный тип!")


async def free_from_prison(message: Message, sub_tier: SubscriptionTier = SubscriptionTier.FREE) -> str:
    """Досрочный выход из тюрьмы (только подписчики)."""
    from shared.models.subscription import TIER_FREE_JAIL_PER_DAY

    limit = TIER_FREE_JAIL_PER_DAY.get(sub_tier, 0)
    if limit == 0:
        return "Досрочный выход из тюрьмы доступен только по подписке. /subscribe"
    is_prisoner, _ = Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if not is_prisoner:
        return "Вы не в тюрьме!"
    # Проверка дневного лимита
    from shared.redis_client import get_redis
    from datetime import date

    r = get_redis()
    key = f"free:{message.from_user.id}:{date.today().isoformat()}"
    used = int(r.get(key) or 0)
    if used >= limit:
        return f"Лимит выходов из тюрьмы на сегодня исчерпан ({used}/{limit}). Завтра сможете снова."
    freed = Prison.free_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if not freed:
        return "Вы не в тюрьме!"
    r.incr(key)
    r.expire(key, 86400)
    return f"Вы досрочно освобождены из тюрьмы! Использовано выходов сегодня: {used + 1}/{limit}."


async def profile(message: Message) -> tuple[str, GroupUserOrm]:
    m_user = message.from_user
    user_orm = await GroupUserOrm.get_group_user(m_user.id, message.chat.id)
    if user_orm is None:
        user_orm = await GroupUserOrm.insert_or_update_group_user(m_user.id, message.chat.id, money=0)
    vasya_coin = declension_word_by_number(user_orm.money, "васякоинов", "васякоин", "васякоина")
    await UserOrm.insert_or_update_user(
        user_orm.user_id,
        first_name=m_user.first_name,
        last_name=m_user.last_name,
        username=m_user.username,
    )
    profile_text = (
        f"Профиль:\n"
        f"    {html.bold('Пользователь')}: {await user_orm.mention_link_html()}\n"
        f"    {html.bold('Баланс')}: {user_orm.money} {vasya_coin}"
    )
    return profile_text, user_orm


async def profile_for_chat(user_id: int, chat_id: int) -> str:
    user = await GroupUserOrm.get_group_user(user_id, chat_id)
    if not user:
        return "Пользователь не найден в этом чате"
    db_user = await UserOrm.get_user_by_id(user_id)
    vasya_coin = declension_word_by_number(user.money, "васякоинов", "васякоин", "васякоина")
    username_display = f"@{db_user.username}" if db_user and db_user.username else (db_user.first_name if db_user else "")
    return (
        f"Профиль в этом чате:\n"
        f"    {html.bold('Пользователь')}: {username_display}\n"
        f"    {html.bold('Баланс')}: {user.money} {vasya_coin}"
    )


async def get_user_by_message(message: Message, bot: aiogram.Bot) -> tuple[GroupUserOrm | None, AiogramUser | None]:
    victim_user_orm: GroupUserOrm | None = None
    victim_user_message: AiogramUser | None = None
    if message.entities:
        for entity in message.entities:
            if victim_user_orm is not None:
                break
            if entity.user:
                victim_user_orm = await GroupUserOrm.get_group_user(entity.user.id, message.chat.id)
                victim_user_message = entity.user
            else:
                username_offset, username_length = entity.offset, entity.length
                username = message.text[username_offset:username_offset + username_length]
                pyrogram_user = await get_user_by_username(message.chat.id, username)
                if pyrogram_user is not None:
                    user_id = pyrogram_user.id
                    victim_user_message = (await bot(GetChatMember(chat_id=message.chat.id, user_id=user_id))).user
                    victim_user_orm = await GroupUserOrm.get_group_user(victim_user_message.id, message.chat.id)
    if victim_user_orm is None:
        if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
            reply_user = message.reply_to_message.from_user
            victim_user_orm = await GroupUserOrm.get_group_user(reply_user.id, message.chat.id)
            victim_user_message = reply_user
    return victim_user_orm, victim_user_message


async def transfer(message: Message, bot: aiogram.Bot, money: list[Any]) -> str:
    if money:
        try:
            money = int(money[0])
            if money <= 0:
                return "Сумма не может быть отрицательной"
        except ValueError:
            return "Укажите сумму перевода. Это должно быть число больше 0"
    else:
        return "Укажите сумму перевода"

    group_user_orm_from = await get_group_user(message)
    if group_user_orm_from.money < money:
        return "У вас недостаточно денег!"
    is_prisoner, prison_time = Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if is_prisoner:
        next_time, at_time = next_activity_from_seconds(prison_time)
        return (
            f"Вы не можете переводить пока находитесь в тюрьме!\n"
            f"Следующая возможность через {html.bold(next_time)}\n"
            f"{html.italic(at_time)} (GMT+3)"
        )

    user_orm_to, user_message_to = await get_user_by_message(message, bot)
    if user_orm_to is None:
        return "Вы не выбрали кому перевести деньги!"
    if message.from_user.id == user_message_to.id:
        return "Нельзя переводить самому себе!"

    await TransactionOrm.insert_transaction(
        group_user_orm_from.id, user_orm_to.id, TransactionType.USER_TRANSFER, money
    )
    await group_user_orm_from.money_minus(money)
    await user_orm_to.money_plus(money)
    vasya_coin = declension_word_by_number(money, "васякоинов", "васякоин", "васякоина")
    return f"Вы перевели {await user_orm_to.mention_link_html()} {money} {vasya_coin}"


async def kill(message: Message, bot: aiogram.Bot) -> str:
    is_prisoner, prison_time = Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id)
    if is_prisoner:
        next_time, at_time = next_activity_from_seconds(prison_time)
        return (
            f"Вы не можете убивать пока находитесь в тюрьме!\n"
            f"Следующая активность через {html.bold(next_time)}\n"
            f"{html.italic(at_time)} (GMT+3)"
        )
    user_orm_to, user_message_to = await get_user_by_message(message, bot)
    if user_orm_to is None:
        return "Вы не выбрали кого убить!"
    if message.from_user.id == user_message_to.id:
        return "Нельзя убить самого себя!"
    return html.bold(f"🔫 Вы застрелили пользователя {await user_orm_to.mention_link_html()}!")


async def get_top_users_money(message: Message, *, limit: int = 10) -> str:
    users = await GroupUserOrm.get_group_users_top_money_by_telegram_chat_id(message.chat.id, limit=limit)
    limit_count = limit if len(users) > limit else len(users)
    return html.bold(f"💰 Топ {limit_count} пользователей по количеству денег:") + "\n" + "\n".join(
        [
            f"{i + 1}. {await user.mention_link_html()} - {user.money} "
            + declension_word_by_number(user.money, "васякоинов", "васякоин", "васякоина")
            for i, user in enumerate(users)
        ]
    )


# Импорт datetime для type hint
from datetime import datetime  # noqa: E402
