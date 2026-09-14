"""FastAPI / WebApp entrypoint — separate process from the Telegram bot.

Run:
  python src/api_app.py

Talks to the bot via RabbitMQ (see messaging.rabbitmq).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from time import sleep

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.append(str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from messaging.rabbitmq import ensure_bus
from utils.logger import setup_logging

setup_logging(settings.ENV, settings.LOG_DIR, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

fastapi_app = FastAPI(title="Telegram Bot WebApp API")

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

webapp_static_path = os.path.join(os.path.dirname(__file__), "webapp", "static")
if os.path.exists(webapp_static_path):
    fastapi_app.mount(
        "/webapp", StaticFiles(directory=webapp_static_path, html=True), name="webapp"
    )
    logger.info("Статика WebApp примонтирована на /webapp из %s", webapp_static_path)
else:
    logger.warning("Путь к статике WebApp не найден: %s", webapp_static_path)


def register_routers() -> None:
    try:
        from api.routes import casino, minigames, user

        fastapi_app.include_router(user.router)
        fastapi_app.include_router(casino.router)
        fastapi_app.include_router(minigames.router)
        logger.info("API роутеры зарегистрированы: user, casino, minigames")
    except ImportError:
        logger.exception("Не удалось импортировать API-роуты")


async def _on_bus_event(routing_key: str, payload: dict) -> None:
    """Handle events from the bot (extend as needed)."""
    logger.debug("API bus event key=%s payload=%s", routing_key, payload)


async def start_bus_consumer() -> None:
    bus = await ensure_bus()
    if not bus.connected:
        return
    await bus.consume(
        queue_name="vasya.api",
        binding_keys=["bot.#"],
        handler=_on_bus_event,
    )


async def main() -> None:
    register_routers()
    bus_task = asyncio.create_task(start_bus_consumer())

    config = uvicorn.Config(
        app=fastapi_app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Запуск FastAPI на %s:%s", settings.API_HOST, settings.API_PORT)
    try:
        await server.serve()
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
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка API...")
        sleep(1)
        raise SystemExit(0)
