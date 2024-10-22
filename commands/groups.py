import random

from aiogram.filters import Command
from aiogram.enums import ChatType, ContentType, ParseMode
from aiogram import Router, F
from aiogram.types import Message, URLInputFile

from commands import func
from config import settings
from models import Messages, ChatGroupSettings
from utils.Filters import ChatTypeFilter, BotNameFilter
from utils.answer_type import AnswerType
from utils.db import generate_text


router_groups = Router()


# https://core.telegram.org/bots/api#html-style
help_text = """<b>Список команд:</b>

<b>• Вася шанс [от 0 до 100] —</b> изменит шанс отправки сообщения

<b>• Вася выбери [значение 1 или значение 2] —</b> выберет одно из предложенного 

<b>• Вася кот —</b> отправит картинку  котика

<b>• Вася кот [текст сообщения] —</b>  отправит картинку котика с текстом

<b>• Вася ответь [текст сообщения] —</b> ответит да/нет"""


@router_groups.message(Command('help'))
async def get_help(message):
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router_groups.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    BotNameFilter(bot_names=settings.BOT_NAMES),
    F.text
    & (F.content_type == ContentType.TEXT)
    & (F.text[0] != '/')
)
async def answer_by_bot_name(message: Message):
    arr_msg = message.text.split()[1:]
    match arr_msg:
        case []:
            answer_type = AnswerType.Text
            messages = [msg.text for msg in await Messages.get_messages(message.chat.id)]
            answer = generate_text(messages)
        case 'шанс', chance:
            answer_type = AnswerType.Text
            answer = await func.set_chance(message, chance)
        case 'ответь', 'гиф', *_:
            answer_type = AnswerType.Animation
            animation, answer = await func.yesno()
        case 'ответь', *_:
            answer_type = AnswerType.Text
            animation, answer = await func.yesno()
        case 'выбери', *words:
            answer_type = AnswerType.Text
            answer = func.choice(words)
        case 'кот', *text:
            answer_type = AnswerType.Photo
            url = 'https://cataas.com/cat'
            if text:
                url = 'https://cataas.com/cat/says/' + ' '.join(text) + '?fontSize=50&fontColor=white'
            photo = URLInputFile(url)
            answer = 'Держи котика'
        case _:
            answer_type = AnswerType.Text
            answer = 'Я ничего не понял, что ты хочешь от меня'

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


@router_groups.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    F.text &
    (F.content_type == ContentType.TEXT) &
    F.text[0] != '/'
)
async def echo(message: Message):
    if message.text is None or message.via_bot:
        return

    await Messages.insert_message(message.chat.id, message.text.replace('@', ''))

    chance = (await ChatGroupSettings.get_chance(message.chat.id)).answer_chance
    if random.randint(1, 100) <= chance:
        messages = [msg.text for msg in await Messages.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)
