from datetime import datetime as dt, timedelta as td
import random

import aiohttp
import pyrogram.errors
from pyrogram.enums import ChatMemberStatus
from aiogram.types import Message, ChatMemberUpdated, User
from aiogram import html

from models import TelegramChatOrm, UserOrm, GroupUserOrm, ProfessionOrm, WorkActivityOrm
from run import app

MEMBER_TYPE_ADMIN = (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)


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
            await UserOrm.insert_or_update_user(member.user)
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
    await UserOrm.insert_or_update_user(member.user)
    await GroupUserOrm.insert_or_update_group_user(member.user.id, event.chat.id, chat_member_status=member.status)


async def set_chance(message: Message, chance: int):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    chance = int(chance)
    if chance > 100 or chance < 0:
        raise ValueError('Шанс должен быть числом от 0 до 100')
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


async def work(message: Message):
    m_user = message.from_user
    user = await GroupUserOrm.get_group_user(message.from_user.id, message.chat.id)
    last_user_work_activity = await WorkActivityOrm.get_last_work_activity_by_group_user_id(user.id)
    h6 = td(hours=6)
    if last_user_work_activity:
        delta = dt.now() - last_user_work_activity.created_at
        if h6 > delta:
            next_work_seconds = (h6 - delta).seconds
            next_work_str = (dt.now() + (h6 - delta)).strftime("%Y-%m-%d в %H:%M:%S")
            hours, minutes = next_work_seconds // 3600, next_work_seconds % 3600 // 60
            hours_str = declension_word_by_number(hours, 'часов', 'час', 'часа')
            minutes_str = declension_word_by_number(minutes, 'минут', 'минута', 'минуты')
            hours_and_minutes_str = f'{hours} {hours_str} {minutes} {minutes_str}'

            return (f'Вы еще не отдохнули.\n'
                    f'Следующая работа будет доступна через {html.bold(hours_and_minutes_str)}\n'
                    f'{html.italic(next_work_str)} (GMT+3)')
    profession = random.choice(await ProfessionOrm.get_all_profession())
    income = random.randint(1, 10)
    vasya_coin = declension_word_by_number(income, 'васякоинов', 'васякоин', 'васякоина')
    await user.money_plus(income)
    await WorkActivityOrm.insert_work_activity(profession.id, user.id, income)

    work_text = (f'{m_user.mention_html(m_user.username)} устраивается на должность {html.bold(html.italic(profession.name))} '
                 f'и зарабатывает {income} {vasya_coin}')
    return work_text


async def profile(message: Message):
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
