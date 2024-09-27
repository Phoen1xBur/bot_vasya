import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from models import Messages
from utils.Filters import ChatTypeFilter
from utils.db import create_tables

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()


@dp.message(Command('start'))
async def start(message: Message):
    await message.answer('Привет!')


@dp.message(
    ChatTypeFilter(chat_type=[ChatType.GROUP, ChatType.SUPERGROUP]),
    F.text &
    F.text[0] != '/'
)
async def echo(message: Message):
    await Messages.insert_message(message.chat.id, message.text)


async def on_startup():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        create_tables()
        # logging.basicConfig(level=logging.DEBUG)
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        print('Stopping...')
