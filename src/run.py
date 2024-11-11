import asyncio
import redis as redis_package

from aiogram import Bot, Dispatcher
from pyrogram import Client

from config import settings


"""Fix utils"""
from utils.fix.fix_pyrogram import *  # noqa
"""End fix"""

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()

app = Client(
    'vasya_fun_bot',
    settings.API_ID,
    settings.API_HASH
)

redis = redis_package.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)


async def on_startup():
    from handlers import routers

    dp.include_routers(
        *routers
    )
    await bot.set_my_commands(settings.MY_COMMANDS)
    bot.default.parse_mode = 'HTML'
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        print('Stopping...')
