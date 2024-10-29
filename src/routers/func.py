import pyrogram.errors
from aiogram.types import Message, ChatMemberUpdated
from random import random

from pyrogram.enums import ChatMemberStatus

from src.models import TelegramChatOrm, UserOrm, GroupUserOrm
import aiohttp

from src.run import app

MEMBER_TYPE_ADMIN = (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)


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
            await UserOrm.insert_or_update_user(member.user.id)
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
    await UserOrm.insert_or_update_user(member.user.id)
    await GroupUserOrm.insert_or_update_group_user(member.user.id, event.chat.id, chat_member_status=member.status)


async def set_chance(message: Message, chance: int):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    chance = int(chance)
    if chance > 100 or chance < 0:
        raise ValueError('Шанс должен быть числом от 0 до 100')
    answer = f'Шанс сообщения изменен на {chance}'
    await TelegramChatOrm.change_answer_chance(message.chat.id, chance)

    return answer


def choice(words):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    words_lower = list(map(lambda text: text.lower(), words))

    count_or = words_lower.count('или')

    if count_or == 0 or count_or > 1:
        return 'В предложении должен присутствовать один выбор посредством ИЛИ'

    if words_lower[0] == 'или' or words_lower[-1] == 'или':
        return 'Выбор ИЛИ не должен находится в начале или конце'

    index_or = words_lower.index('или')
    answer = ' '.join(words[:index_or] if random() < .5 else words[index_or + 1:])

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
