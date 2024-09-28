import asyncio
import logging
import random

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ContentType
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from models import Messages
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
    F.text[0] != '/'
)
async def echo(message: Message):
    if message.text is None:
        return
    await Messages.insert_message(message.chat.id, message.text)

    if random.randint(0, 100) <= 20:
        messages = [msg.text for msg in await Messages.get_messages(message.chat.id)]
        text = generate_text(messages)
        print(f'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! {text}')
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
