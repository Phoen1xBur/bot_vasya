import random

from aiogram.methods import SendAnimation, SendMessage

from config import redis

import aiogram
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from keyboards.inline_kb_profile_change_settings import profile_change_settings
from keyboards.webapp_test import build_inline_kb_start
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
                if len(chance) > 0:
                    chance = chance[0]
                    answer = await func.set_chance(message, chance)
                else:
                    answer, chance = await func.get_chance(message)
                redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
            else:
                answer = 'Эта команда доступна только для администраторов группы'
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
        case 'кто' | 'кого', *words:
            members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(message.chat.id)
            random_member: GroupUserOrm = random.choice(members)
            answer = f'Я думаю {await random_member.mention_link_html()} ' + ' '.join(words)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'кот', *text:
            command = CommandCat(chat_id=chat_id, text=text)
        case 'кража', *text:
            answer = await func.rob(message, bot)
            print(answer)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'перевод', *text:
            answer = await func.transfer(message, bot, text)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'убить', *text:
            answer = await func.kill(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'топ', *text:
            return await top_users(message)
        case ('тест' | 'test', ):
            answer, keyboard = await func.test(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer, reply_markup=keyboard)
        case _:
            command = CommandUndefined(chat_id=chat_id)
    if command:
        await bot(command)


@router.message(Command('profile'))
async def profile(message: Message):
    answer, user_orm = await func.profile(message)
    notification = '❌ Выключить' if user_orm.can_tag else '✅ Включить'
    await message.answer(
        answer, reply_markup=await profile_change_settings(
            message.from_user.id,
            message.chat.id,
            notification
        )
    )


@router.message(Command('top_users'))
async def top_users(message: Message):
    answer = await func.get_top_users_money(message)
    await message.answer(answer)


@router.message(Command('work'))
async def work(message: Message):
    answer = await func.work(message)
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
        try:
            redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
        except Exception as e:
            print(f'Redis error: {e}')
    if random.randint(1, 100) <= int(chance):
        messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)


@router.message(Command('profile_test'))
async def profile_test(message: Message):
    inline_kb = await build_inline_kb_start(message.chat.id, 'profile')
    await message.answer('Быстрее смотри свой профиль!', reply_markup=inline_kb)
