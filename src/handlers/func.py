from datetime import datetime as dt, timedelta as td, datetime
from math import ceil
import random

import aiogram
import aiohttp
import pyrogram.errors
from pyrogram.enums import ChatMemberStatus
from aiogram.types import Message, ChatMemberUpdated, User as AiogramUser
from aiogram.methods import GetChatMember
from aiogram import html

from models import TelegramChatOrm, UserOrm, GroupUserOrm, ProfessionOrm, TransactionOrm
from models.money import Prison
from run import app
from utils.enums import TransactionType

MEMBER_TYPE_ADMIN = (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
H6 = td(hours=6)
H12 = td(hours=12)


def declension_word_by_number(number: int, word_form_0, word_form_1, word_form_2: str):
    """Возвращает склоняемое слово относительно числа
    example:
    declension_word_by_number(1, 'день', 'дня', 'дней') -> 'день'
    declension_word_by_number(2, 'день', 'дня', 'дней') -> 'дня'
    declension_word_by_number(5, 'день', 'дня', 'дней') -> 'дней'"""
    if number % 10 == 1 and number % 100 != 11:
        return word_form_1
    elif 1 < number % 10 < 5 and (number % 100 < 10 or number % 100 >= 20):
        return word_form_2
    else:
        return word_form_0


async def get_group_user(message: Message):
    group_user: GroupUserOrm = await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    if not group_user:
        await TelegramChatOrm.insert_or_update_telegram_chat(message.chat.id)
        await update_users(message)
        return await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    return group_user


async def update_users(event: ChatMemberUpdated | Message):
    async with app:
        async for member in app.get_chat_members(event.chat.id):
            if member.user.is_bot:
                continue
            await UserOrm.insert_or_update_user(member.user.id, member.user)
            await GroupUserOrm.insert_or_update_group_user(
                member.user.id, event.chat.id, chat_member_status=member.status
            )


async def update_user(event: ChatMemberUpdated):
    async with app:
        try:
            member = await app.get_chat_member(event.chat.id, event.new_chat_member.user.id)
        except pyrogram.errors.bad_request_400.UserNotParticipant:
            # Пользователь ушел с группы - меняем статус на Left
            await GroupUserOrm.insert_or_update_group_user(
                event.new_chat_member.user.id, event.chat.id,
                chat_member_status=ChatMemberStatus.LEFT
            )
            return
    if member.user.is_bot:
        return
    await UserOrm.insert_or_update_user(member.user.id, member.user)
    await GroupUserOrm.insert_or_update_group_user(member.user.id, event.chat.id, chat_member_status=member.status)


async def get_user_by_username(chat_id: int, username: str) -> pyrogram.types.User:
    async with app:
        try:
            member = await app.get_chat_member(chat_id, username)
            member = member.user
        except pyrogram.errors.bad_request_400.UserNotParticipant:
            member = None
        return member


async def set_chance(message: Message, chance: int):
    answer_error = 'Шанс должен быть числом от 0 до 100'
    try:
        chance = int(chance)
    except ValueError:
        return answer_error
    if chance > 100 or chance < 0:
        return answer_error
    answer = f'Шанс сообщения изменен на {chance}'
    await TelegramChatOrm.change_answer_chance(message.chat.id, chance)

    return answer


def choice_words(words):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    words_lower = list(map(lambda text: text.lower(), words))

    count_or = words_lower.count('или')

    if count_or == 0 or count_or > 1:
        return 'В предложении должен присутствовать один выбор посредством ИЛИ'

    if words_lower[0] == 'или' or words_lower[-1] == 'или':
        return 'Выбор ИЛИ не должен находится в начале или конце'

    index_or = words_lower.index('или')
    answer = ' '.join(words[:index_or] if random.random() < .5 else words[index_or + 1:])

    return answer


async def yesno() -> tuple:
    url = 'https://yesno.wtf/api'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            json = await response.json()
    animation, answer_en = json['image'], json['answer']
    match answer_en:
        case 'yes':
            answer_ru = 'Да'
        case 'no':
            answer_ru = 'Нет'
        case 'maybe':
            answer_ru = 'Может быть'
        case _:
            answer_ru = 'Спроси позже...'
    return animation, answer_ru


def next_activity(created_at: datetime, after_time: td = H6) -> (bool, str, str):
    delta = dt.now() - created_at
    can_activity = after_time < delta
    next_time = ''
    at_time = ''
    if not can_activity:
        next_work_seconds = (after_time - delta).seconds
        next_work_str = (dt.now() + (after_time - delta)).strftime("%Y-%m-%d в %H:%M:%S")
        hours, minutes = next_work_seconds // 3600, next_work_seconds % 3600 // 60
        hours_str = declension_word_by_number(hours, 'часов', 'час', 'часа')
        minutes_str = declension_word_by_number(minutes, 'минут', 'минута', 'минуты')
        hours_and_minutes_str = f'{hours} {hours_str} {minutes} {minutes_str}'
        next_time = hours_and_minutes_str
        at_time = next_work_str
    return can_activity, next_time, at_time


async def work(message: Message) -> str:
    m_user = message.from_user
    group_user_from = await get_group_user(message)
    last_trans = await TransactionOrm.get_last_transaction_by_params(
        transaction_type=TransactionType.WORK,
        group_user_to_id=group_user_from.id
    )
    # ПРОВЕРКА НА ВОЗМОЖНОСТЬ РАБОТЫ
    if last_trans:
        can_work, next_time, at_time = next_activity(last_trans.created_at, H6)
        if not can_work:
            return (f'Вы еще не отдохнули.\n'
                    f'Следующая работа будет доступна через {html.bold(next_time)}\n'
                    f'{html.italic(at_time)} (GMT+3)')
    # РАБОТАЕМ
    profession: ProfessionOrm = random.choice(await ProfessionOrm.get_all_profession())
    # заработок относительно минимума и максимума профессии включительно
    income = random.randint(profession.money_min, profession.money_max)
    vasya_coin = declension_word_by_number(income, 'васякоинов', 'васякоин', 'васякоина')
    await group_user_from.money_plus(income)
    await TransactionOrm.insert_transaction(None, group_user_from.id, TransactionType.WORK, income)

    work_text = (
        f'{m_user.mention_html(m_user.username)} устраивается на должность {html.bold(html.italic(profession.name))} '
        f'и зарабатывает {income} {vasya_coin}'
    )
    if profession.accompanying_text:
        work_text += f'\n\n{html.italic(profession.accompanying_text)}'
    return work_text


async def profile(message: Message) -> str:
    m_user = message.from_user
    user = await GroupUserOrm.get_group_user(m_user.id, message.chat.id)
    vasya_coin = declension_word_by_number(user.money, 'васякоинов', 'васякоин', 'васякоина')
    await UserOrm.insert_or_update_user(
        user.user_id,
        first_name=m_user.first_name,
        last_name=m_user.last_name,
        username=m_user.username
    )

    profile_text = f'''Профиль:
    {html.bold('Пользователь')}: {m_user.mention_html(m_user.username)}
    {html.bold('Баланс')}: {user.money} {vasya_coin}'''

    return profile_text


async def get_user_by_message(message: Message, bot: aiogram.Bot) -> (GroupUserOrm, AiogramUser):
    victim_user_orm: GroupUserOrm = None
    victim_user_message: AiogramUser = None

    # Узнаем пользователя, у которого нужно украсть
    # Проверка по username'у
    if message.entities:
        for entity in message.entities:
            if victim_user_orm is not None:
                break
            if entity.user:
                victim_user_orm = await GroupUserOrm.get_group_user(entity.user.id, message.chat.id)
                victim_user_message = entity.user
            else:
                username_offset, username_length = entity.offset, entity.length
                username = message.text[username_offset:username_offset+username_length]
                pyrogram_user = await get_user_by_username(message.chat.id, username)
                if pyrogram_user is not None:
                    user_id = pyrogram_user.id
                    victim_user_message = (await bot(GetChatMember(chat_id=message.chat.id, user_id=user_id))).user
                    victim_user_orm = await GroupUserOrm.get_group_user(victim_user_message.id, message.chat.id)

    # Проверка по reply_to_message
    if victim_user_orm is None:
        if message.reply_to_message and not message.reply_to_message.from_user.is_bot:
            reply_user = message.reply_to_message.from_user
            victim_user_orm = await GroupUserOrm.get_group_user(reply_user.id, message.chat.id)
            victim_user_message = reply_user

    return victim_user_orm, victim_user_message


async def rob(message: Message, bot: aiogram.Bot) -> str:
    # Проверяем, есть ли у пользователя возможность грабить (В тюрьме ли он, или возможность по времени)
    group_user_from = await get_group_user(message)
    last_trans = await TransactionOrm.get_last_transaction_by_params(
        transaction_type=TransactionType.ROB,
        group_user_to_id=group_user_from.id
    )
    # ПРОВЕРКА НА ВОЗМОЖНОСТЬ КРАЖИ
    if Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id):
        return 'Вы не можете грабить пока находитесь в тюрьме!'
    if last_trans:
        can_rob, next_time, at_time = next_activity(last_trans.created_at, H6)
        if not can_rob:
            return (f'За вами пристально следят.\n'
                    f'Следующая работа будет доступна через {html.bold(next_time)}\n'
                    f'{html.italic(at_time)} (GMT+3)')

    # Находим пользователя, которого нужно ограбить
    victim_user_orm: GroupUserOrm
    victim_user_message: AiogramUser
    victim_user_orm, victim_user_message = await get_user_by_message(message, bot)

    # Если пользователя которого нужно ограбить нет, сообщаем об этом
    if victim_user_orm is None:
        return 'Вы не выбрали кого обворовать!'

    if message.from_user.id == victim_user_message.id:
        return 'Нельзя воровать у самого себя!'

    if Prison.is_prisoner(chat_id=message.chat.id, user_id=victim_user_message.id):
        return 'Этот пользователь в тюрьме!'

    if victim_user_orm.money < 10:
        return 'У этого пользователя недостаточно денег!'

    proc = victim_user_orm.money / 100
    money = random.randint(ceil(proc), ceil(proc * 30))
    await TransactionOrm.insert_transaction(
        victim_user_orm.id, group_user_from.id, TransactionType.ROB, money
    )
    await group_user_from.money_plus(money)
    await victim_user_orm.money_minus(money)
    vasya_coin = declension_word_by_number(money, 'васякоинов', 'васякоин', 'васякоина')
    return f"Вы украли у {victim_user_message.mention_html()} {money} {vasya_coin}"


async def transfer(message: Message, bot: aiogram.Bot, money: int) -> str:
    group_user_orm_from = await get_group_user(message)

    if group_user_orm_from.money < money:
        return 'У вас недостаточно денег!'
    # Проверка в тюрьме ли человек, который переводит
    if Prison.is_prisoner(chat_id=message.chat.id, user_id=message.from_user.id):
        return 'Вы не можете переводить пока находитесь в тюрьме!'

    # Находим пользователя, которому нужно перевести
    user_orm_to: GroupUserOrm
    user_message_to: AiogramUser
    user_orm_to, user_message_to = await get_user_by_message(message, bot)
    if user_orm_to is None:
        return 'Вы не выбрали кому перевести деньги!'

    if message.from_user.id == user_message_to.id:
        return 'Нельзя переводить самому себе!'

    # Проверка в тюрьме ли человек, которому нужно перевести
    if Prison.is_prisoner(chat_id=message.chat.id, user_id=user_message_to.id):
        return 'Вы не можете грабить пока находитесь в тюрьме!'

    await TransactionOrm.insert_transaction(
        group_user_orm_from.id, user_orm_to.id, TransactionType.USER_TRANSFER, money
    )
    await group_user_orm_from.money_minus(money)
    await user_orm_to.money_plus(money)
    vasya_coin = declension_word_by_number(money, 'васякоинов', 'васякоин', 'васякоина')
    return f"Вы перевели {user_message_to.mention_html()} {money} {vasya_coin}"
