import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from utils.db import create_tables

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()


@dp.message(Command('start'))
async def start(message: Message):
    await message.answer('Привет!')


async def on_startup():
    from commands.groups import router_groups

    dp.include_routers(
        router_groups,
    )

    await bot.set_my_commands(settings.MY_COMMANDS)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        create_tables()
        # logging.basicConfig(level=logging.DEBUG)
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        print('Stopping...')
