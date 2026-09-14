"""Telegram bot entrypoint (no FastAPI — see api_app.py)."""

import asyncio
import logging
import sys
from pathlib import Path
from time import sleep

from aiogram import Bot, Dispatcher
from pyrogram import Client

sys.path.append(str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from config import settings, redis
from utils.logger import setup_logging
from utils.auto_delete_message_service import AutoDeleteService
from messaging.rabbitmq import ensure_bus

"""Fix utils"""
from utils.fix.fix_pyrogram import *  # noqa
"""End fix"""

setup_logging(settings.ENV, settings.LOG_DIR, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()

auto_delete_service = AutoDeleteService(redis, bot)

app = Client(
    "vasya_fun_bot",
    settings.API_ID,
    settings.API_HASH,
)


async def start_bot() -> None:
    from handlers import routers
    from middleware import middlewares, auto_delete_message

    dp.include_routers(*routers)
    dp.update.middleware(
        auto_delete_message.AutoDeleteMiddleware(auto_delete_service)
    )
    for middleware in middlewares:
        dp.update.middleware(middleware)

    await bot.set_my_commands(settings.MY_COMMANDS)
    bot.default.parse_mode = "HTML"
    await dp.start_polling(bot)


async def start_bus_consumer() -> None:
    """Listen for API → bot events (e.g. webapp actions). Optional."""
    bus = await ensure_bus()
    if not bus.connected:
        logger.info("RabbitMQ offline — bot runs without message bus")
        return

    async def on_event(routing_key: str, payload: dict) -> None:
        logger.debug("Bot bus event key=%s payload=%s", routing_key, payload)

    await bus.consume(
        queue_name="vasya.bot",
        binding_keys=["api.#"],
        handler=on_event,
    )


async def on_startup() -> None:
    bus_task = asyncio.create_task(start_bus_consumer())
    bot_task = asyncio.create_task(start_bot())
    cleaner_task = asyncio.create_task(auto_delete_service.run_cleaner())
    try:
        await asyncio.gather(bot_task, cleaner_task)
    finally:
        bus_task.cancel()
        try:
            await bus_task
        except asyncio.CancelledError:
            pass
        bus = await ensure_bus()
        await bus.close()


if __name__ == "__main__":
    try:
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        logger.info("Остановка...")
        sleep(2)
        raise SystemExit(0)
    except Exception:
        logger.exception("Необработанная ошибка")
