import random

from aiogram.methods import SendAnimation, SendMessage

from config import redis

import aiogram
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from models.money import TransactionOrm
from . import func
from config import settings
from models import MessageOrm, TelegramChatOrm, GroupUserOrm
from utils.filters import ChatTypeFilter, MessageTypeFilter, BotNameFilter
from utils.enums import ChatType, ContentType, TransactionType
from utils.utils import generate_text
from .command import CommandUndefined, CommandCat

router = Router(name=__name__)
router.message.filter(
    # События только из:
    # Тип чата: группа/супергруппа
    ChatTypeFilter(
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ),
    # Тип сообщения: ТЕКСТ
    MessageTypeFilter(
        ContentType.TEXT,
    ),
    # Пока не работает: TypeError: unsupported callable
    # Сообщение сгенерированное НЕ ботом
    # not F.via_bot,
    # Тип пересылки сообщения: Отсутствует
    # F.forward_origin is None
)


@router.message(
    BotNameFilter(bot_names=settings.BOT_NAMES),
    (F.text[0] != '/')
)
async def answer_by_bot_name(message: Message, bot: aiogram.Bot):
    arr_msg = message.text.split()[1:]
    group_user: GroupUserOrm = await func.get_group_user(message)
    chat_id = message.chat.id

    match arr_msg:
        case []:
            messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
            answer = generate_text(messages)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'шанс', *chance:
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                chance = chance[0] if len(chance) > 0 else -1
                answer = await func.set_chance(message, chance)
                redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
            else:
                answer = 'Эта привилегия доступна только для администраторов группы'
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'ответь', *words:
            animation, answer = await func.yesno()
            gif = words and words[0] == 'гиф'
            if gif:
                command = SendAnimation(chat_id=chat_id, animation=animation, caption=answer)
            else:
                command = SendMessage(chat_id=chat_id, text=answer)
        case 'выбери', *words:
            answer = func.choice_words(words)
            command = SendMessage(chat_id=chat_id, text=answer)
        case ('работа' | 'работать', ):
            return await work(message)
        case 'профиль', *_:
            return await profile(message)
        case 'вероятность', *words:
            text = ' '.join(words)
            answer = f'Вероятность {text}: {random.randint(0, 100)}%'
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'кто', *words:
            members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(message.chat.id)
            random_member: GroupUserOrm = random.choice(members)
            member = await bot.get_chat_member(random_member.telegram_chat_id, random_member.user_id)
            answer = f'Я думаю {member.user.mention_html()} ' + ' '.join(words)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'кот', *text:
            command = CommandCat(chat_id=chat_id, text=text)
        case 'кража', *text:
            return await rob(message)
        case _:
            command = CommandUndefined(chat_id=chat_id)
    if command:
        await bot(command)


@router.message(Command('profile'))
async def profile(message: Message):
    answer = await func.profile(message)
    await message.answer(answer)


@router.message(Command('work'))
async def work(message: Message):
    answer = await func.work(message)
    await message.answer(answer)


@router.message(Command('rob'))
async def rob(message: Message):
    answer = await func.rob(message)
    await message.answer(answer)


@router.message(
    F.text[0] != '/'
)
async def echo(message: Message):
    if message.text is None:
        return

    if message.via_bot or message.forward_origin:
        return

    group_user: GroupUserOrm = await func.get_group_user(message)

    await MessageOrm.insert_message(group_user.id, message.text.replace('@', ''))

    if message.reply_to_message and message.reply_to_message.from_user.username == 'vasya_fun_bot':
        messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        answer = generate_text(messages)
        await message.answer(answer)
        return

    try:
        chance = redis.get(f'tg_chat_chance:{message.chat.id}')
    except:
        chance = None
    if chance is None:
        chance = (await TelegramChatOrm.get_chance(message.chat.id)).answer_chance
        redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
    if random.randint(1, 100) <= int(chance):
        messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)
