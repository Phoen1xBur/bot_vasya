"""Telegram-бот (polling + RabbitMQ consumer).

Запуск:
  python -m src.run_bot

Не запускает FastAPI. Общается с API через shared.api_client.
"""

import asyncio
import logging
import sys
from pathlib import Path
from time import sleep

# Python 3.14: pyrogram calls get_event_loop() at import time.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from aiogram import Bot, Dispatcher
from pyrogram import Client

_ROOT = Path(__file__).resolve().parent.parent
_SRC = Path(__file__).resolve().parent
for _p in (_SRC, _ROOT):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)

from shared.bot_identity import init_bot_identity  # noqa: E402
from shared.config import get_settings  # noqa: E402
from shared.logger import setup_logging  # noqa: E402

settings = get_settings()
setup_logging(settings.ENV, settings.LOG_DIR, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

from utils.fix.fix_pyrogram import *  # noqa: F401,F403,E402

bot = Bot(token=settings.TOKEN)
dp = Dispatcher()

# Имя сессии Pyrogram — это идентификатор файла, а не @username бота.
# bot_token: старт без интерактивного ainput (phone/bot token).
_api_id = settings.API_ID
try:
    _api_id = int(_api_id) if _api_id not in (None, "") else 0
except (TypeError, ValueError):
    _api_id = 0
app = Client(
    "vasya_session",
    api_id=_api_id,
    api_hash=settings.API_HASH or "",
    bot_token=settings.TOKEN,
)

from utils.auto_delete_message_service import AutoDeleteService  # noqa: E402
from shared.redis_client import get_redis  # noqa: E402

auto_delete_service = AutoDeleteService(get_redis(), bot)


async def start_bot() -> None:
    from handlers import routers
    from middleware import middlewares, auto_delete_message, subscription_tags

    dp.include_routers(*routers)
    dp.update.middleware(auto_delete_message.AutoDeleteMiddleware(auto_delete_service))
    dp.update.middleware(subscription_tags.SubscriptionTagsMiddleware())
    for mw in middlewares:
        dp.update.middleware(mw)

    # Запрашиваем @username и id бота у Telegram один раз — используем
    # во всех пользовательских строках (без хардкода ника).
    await init_bot_identity(bot)
    await bot.set_my_commands(settings.MY_COMMANDS)
    bot.default.parse_mode = "HTML"
    await dp.start_polling(bot, drop_pending_updates=True)


async def start_bus_consumer() -> None:
    """Слушаем события от API (webapp-действия, завершение игр и т.д.)."""
    try:
        from messaging.rabbitmq import ensure_bus

        bus = await ensure_bus()
        if not bus.connected:
            logger.info("RabbitMQ offline — бот без шины")
            return

        async def on_event(routing_key: str, payload: dict) -> None:
            logger.debug("Bot bus event key=%s payload=%s", routing_key, payload)
            # Обработка событий от API (например, рассылка рекламы)
            if routing_key == "ad.send" or routing_key.endswith(".ad.send"):
                await _handle_ad_send(payload)
            elif routing_key == "game.finished" or routing_key.endswith(".game.finished"):
                await _handle_game_finished(payload)

        await bus.consume(queue_name="vasya.bot", binding_keys=["api.#"], handler=on_event)
    except Exception:
        logger.warning("Шина недоступна", exc_info=True)


async def _handle_ad_send(payload: dict) -> None:
    """Рассылка рекламы по выбранным чатам."""
    chat_ids = payload.get("chat_ids", [])
    text = payload.get("text", "")
    link = payload.get("link", "")
    message = f"{text}\n\n🔗 {link}"
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, message)
        except Exception:
            logger.warning("Не удалось отправить рекламу в чат %s", chat_id)


async def _handle_game_finished(payload: dict) -> None:
    """Публикация результата игры в чат-источник."""
    chat_id = payload.get("chat_id")
    text = payload.get("result_text")
    if chat_id and text:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.warning("Не удалось отправить результат игры в чат %s", chat_id)


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
        from messaging.rabbitmq import ensure_bus

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
