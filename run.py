import asyncio
import logging
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ContentType
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from models import Messages, ChatGroupSettings
from utils.Filters import ChatTypeFilter
from utils.db import create_tables, generate_text

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()


@dp.message(Command('start'))
async def start(message: Message):
    await message.answer('Привет!')


@dp.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    F.text &
    (F.content_type == ContentType.TEXT) &
    (F.text[0] != '/') &
    (F.text.lower().startswith('вася'))
)
async def answer_chance(message: Message):
    vasya = 'вася'
    arr_msg = message.text[len(vasya)+1:].split(' ')
    print(arr_msg)
    match arr_msg:
        case ['']:
            messages = [msg.text for msg in await Messages.get_messages(message.chat.id)]
            text = generate_text(messages)
        case 'шанс', chance:
            try:
                chance = int(chance)
                if chance > 100 or chance < 0:
                    raise ValueError
                text = f'Шанс сообщения изменен на {chance}'
                await ChatGroupSettings.change_answer_chance(message.chat.id, chance)
            except ValueError:
                text = 'Шанс должен быть числом от 0 до 100'
        case _:
            text = 'Я ничего не понял, что ты хочешь от меня'

    await message.answer(text)

@dp.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    F.text &
    (F.content_type == ContentType.TEXT) &
    F.text[0] != '/'
)
async def echo(message: Message):
    if message.text is None:
        return
    await Messages.insert_message(message.chat.id, message.text)

    chance = (await ChatGroupSettings.get_chance(message.chat.id)).answer_chance
    if random.randint(1, 100) <= chance:
        messages = [msg.text for msg in await Messages.get_messages(message.chat.id)]
        text = generate_text(messages)
        await message.answer(text)


async def on_startup():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        create_tables()
        # logging.basicConfig(level=logging.DEBUG)
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        print('Stopping...')
