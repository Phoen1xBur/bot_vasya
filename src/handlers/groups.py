import random
from datetime import datetime

from aiogram.methods import SendAnimation, SendMessage

from config import redis

import aiogram
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from keyboards.inline_kb_generate_start import build_inline_kb_start
from keyboards.inline_kb_profile_change_settings import profile_change_settings
from keyboards.inline_kb_minigames import build_inline_kb_minigames_select
from utils.auto_delete_message_service import AutoDeleteService
from . import func
from config import settings
from models import MessageOrm, TelegramChatOrm, GroupUserOrm
from utils.filters import ChatTypeFilter, MessageTypeFilter, BotNameFilter
from utils.enums import ChatType, ContentType, TransactionType
from utils.utils import generate_text, generate_text_from_ai
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
async def answer_by_bot_name(message: Message, bot: aiogram.Bot, message_delete_service: AutoDeleteService):
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
            return await work(message, message_delete_service)
        case 'профиль', *_:
            return await profile(message, message_delete_service)
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
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'перевод', *text:
            answer = await func.transfer(message, bot, text)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'убить', *text:
            answer = await func.kill(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer)
        case 'топ', *text:
            return await top_users(message, message_delete_service)
        case ('minigames' | 'миниигры' | 'игры'), *_:
            try:
                redis.hset(f'mg:lobby:{chat_id}', mapping={'creator_id': message.from_user.id})
            except Exception:
                pass
            keyboard = build_inline_kb_minigames_select()
            command = SendMessage(chat_id=chat_id, text='Выберите мини-игру:', reply_markup=keyboard)
        case ('тест' | 'test', ):
            answer, keyboard = await func.test(message, bot)
            command = SendMessage(chat_id=chat_id, text=answer, reply_markup=keyboard)
        case _:
            messages = [
                {'role': 'system', 'content': 'Ты являешься ботом Васей. Состоишь в чате со множеством людей. Относительно характера и стиля беседы отвечай соответствующе. Если тебя (Васю) что-то спросили, можешь дать полноценный и корректный ответ, насколько ты можешь его дать.'},
                {'role': 'system', 'content': f'Так же помимо того, что старайся отвечать коротко, отвечай по делу, иногда строго по делу. В зависимости от того как тебя спросили. Так же ориентируйся на текущую дату и время, в некоторых вопросах это важно. Текущая дата и время: {datetime.now()}'},
                {'role': 'user', 'content': message.text},
            ]
            response = await generate_text_from_ai(messages)
            answer = response.choices[0].message.content
            command = SendMessage(chat_id=chat_id, text=answer)
            # command = CommandUndefined(chat_id=chat_id)
    if command:
        await bot(command)


@router.message(Command('profile'))
async def profile(message: Message, message_delete_service: AutoDeleteService):
    answer, user_orm = await func.profile(message)
    notification = '❌ Выключить' if user_orm.can_tag else '✅ Включить'
    message_answer = await message.answer(
        answer, reply_markup=await profile_change_settings(
            message.from_user.id,
            message.chat.id,
            notification
        )
    )
    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(message_answer.chat.id, message_answer.message_id)


@router.message(Command('top_users'))
async def top_users(message: Message, message_delete_service: AutoDeleteService):
    answer = await func.get_top_users_money(message)
    message_answer = await message.answer(answer)

    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(message_answer.chat.id, message_answer.message_id)


@router.message(Command('minigames'))
async def minigames(message: Message):
    try:
        redis.hset(f'mg:lobby:{message.chat.id}', mapping={'creator_id': message.from_user.id})
    except Exception:
        pass
    keyboard = build_inline_kb_minigames_select()
    await message.answer('Выберите мини-игру:', reply_markup=keyboard)


@router.message(Command('work'))
async def work(message: Message, message_delete_service: AutoDeleteService):
    answer = await func.work(message)
    message_answer = await message.answer(answer)

    message_delete_service.schedule(message.chat.id, message.message_id)
    message_delete_service.schedule(message_answer.chat.id, message_answer.message_id)


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
        msg_from_db = await MessageOrm.get_messages(message.chat.id)
        # messages = [msg.text for msg in msg_from_db]
        messages = [{'role': 'user', 'content': f'[{msg[1] or msg[2] or msg[3]}] ' + msg[0]} for msg in reversed(msg_from_db)]
        # messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        messages.insert(0, {'role': 'system', 'content': 'В квадратных скобках в начале сообщения всегда отображается имя/ник пользователя. В случае его отсутствия - можешь считать его твоим администратором. Сам ответ не давай с именем в квадратных скобках. Так же это самое первое сообщение в системе.'})
        messages.append({'role': 'system', 'content': 'Ты являешься ботом Васей. Состоишь в чате со множеством людей. Относительно характера и стиля беседы отвечай соответствующе. Если тебя (Васю) что-то спросили, можешь дать полноценный и корректный ответ, насколько ты можешь его дать. Это самое последнее сообщение. Так что читай/отвечай в соответствующем порядке. Чем новее сообщение тем оно важнее.'})
        response = await generate_text_from_ai(messages)
        await message.answer(response.choices[0].message.content)


@router.message(Command('profile_test'))
async def profile_test(message: Message):
    inline_kb = await build_inline_kb_start(message.chat.id, 'profile', '📱 Открыть профиль')
    await message.answer('Быстрее смотри свой профиль!', reply_markup=inline_kb)


@router.message(Command('casino'))
async def casino(message: Message):
    inline_kb = await build_inline_kb_start(message.chat.id, 'casino', '🎰 Открыть казино')
    await message.answer('Вход в казино', reply_markup=inline_kb)
