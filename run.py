import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from pyrogram import Client

from config import settings
from utils.db import create_tables


"""Fix utils"""
from fix.fix_pyrogram import *
"""End fix"""

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()

app = Client(
    'stupid_vasya_bot',
    settings.API_ID,
    settings.API_HASH
)


@dp.message(Command('start'))
async def start(message: Message):
    await message.answer('Привет!')


async def on_startup():
    from commands.groups import router_groups

    dp.include_routers(
        router_groups,
    )

    await bot.set_my_commands(settings.MY_COMMANDS)
    bot.default.parse_mode = 'HTML'
    await dp.start_polling(bot)

    # bot_pyrogram = await asyncio.create_task(app.run())
    # bot_aiogram = await asyncio.create_task(dp.start_polling())
    # await asyncio.gather(bot_aiogram, bot_pyrogram, return_exceptions=True)

if __name__ == '__main__':
    try:
        create_tables()
        # logging.basicConfig(level=logging.DEBUG)
        asyncio.run(on_startup())
        # asyncio.ensure_future(on_startup())
        # asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print('Stopping...')
