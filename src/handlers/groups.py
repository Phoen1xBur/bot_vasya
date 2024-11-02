import random
from run import redis

import aiogram
from aiogram import Router, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import Command

from . import func
from config import settings
from models import MessageOrm, TelegramChatOrm, GroupUserOrm
from utils.filters import ChatTypeFilter, MessageTypeFilter, BotNameFilter
from utils.enums import AnswerType, ChatType, ContentType
from utils.utils import generate_text

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

    match arr_msg:
        case []:
            answer_type = AnswerType.Text
            messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
            answer = generate_text(messages)
        case 'шанс', *chance:
            answer_type = AnswerType.Text
            if group_user.chat_member_status in func.MEMBER_TYPE_ADMIN:
                try:
                    chance = chance[0] if len(chance) > 0 else -1
                    answer = await func.set_chance(message, chance)
                    redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
                except ValueError as e:
                    answer = e.__str__()
            else:
                answer = 'Эта привилегия доступна только для администраторов группы'
        case 'ответь', 'гиф', *_:
            answer_type = AnswerType.Animation
            animation, answer = await func.yesno()
        case 'ответь', *_:
            answer_type = AnswerType.Text
            animation, answer = await func.yesno()
        case 'выбери', *words:
            answer_type = AnswerType.Text
            answer = func.choice_words(words)
        case ('работа' | 'работать', ):
            answer_type = AnswerType.Text
            answer = await func.work(message)
        case 'профиль', *_:
            answer_type = AnswerType.Text
            answer = await func.profile(message)
            await func.update_users(message)
        case 'вероятность', *words:
            answer_type = AnswerType.Text
            user_url = message.from_user.mention_html()
            text = ' '.join(words).replace('Я', user_url).replace('я', user_url)
            answer = f'Вероятность {text}: {random.randint(0, 100)}%'
        case 'кто', *words:
            answer_type = AnswerType.Text
            members = await GroupUserOrm.get_groups_user_by_telegram_chat_id(message.chat.id)
            random_member: GroupUserOrm = random.choice(members)
            member = await bot.get_chat_member(random_member.telegram_chat_id, random_member.user_id)
            answer = f'Я думаю {member.user.mention_html()} ' + ' '.join(words)
        case 'кот', *text:
            answer_type = AnswerType.Photo
            url = 'https://cataas.com/cat'
            if text:
                url = 'https://cataas.com/cat/says/' + ' '.join(text) + '?fontSize=50&fontColor=white'
            photo = URLInputFile(url)
            answer = 'Держи котика'
        case _:
            answer_type = AnswerType.Text
            answer = 'Я ничего не понял, что ты хочешь от меня\nМожешь написать /help@vasya_fun_bot для справки'

    # TODO: Переделать в будущем на message.chat.do(action, *param)
    match answer_type:
        case AnswerType.Text:
            await message.answer(answer)
        case AnswerType.Animation:
            await message.answer_animation(animation=animation, caption=answer)
        case AnswerType.Photo:
            await message.answer_photo(photo=photo, caption=answer)
        # case AnswerType.Video:
        #     await message.answer_video(video=video, caption=answer)
        case _:
            pass
    print(message.text)
    print(answer)


@router.message(Command('profile'))
async def profile(message: Message):
    answer = await func.profile(message)
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

    chance = redis.get(f'tg_chat_chance:{message.chat.id}')
    if chance is None:
        chance = (await TelegramChatOrm.get_chance(message.chat.id)).answer_chance
        redis.set(f'tg_chat_chance:{message.chat.id}', chance, ex=120)
    if random.randint(1, 100) <= int(chance):
        messages = [msg.text for msg in await MessageOrm.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)
