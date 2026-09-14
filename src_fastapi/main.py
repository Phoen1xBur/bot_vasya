"""FastAPI-сервис: WebApp-статика, REST-эндпоинты, БД, платежи, игры, реклама.

Запуск:
  python -m src_fastapi.main
  (или: uvicorn src_fastapi.main:app --host 0.0.0.0 --port 8000)

Не зависит от бота. Бот обращается к этому сервису через HTTP.
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from time import sleep

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import get_settings  # noqa: E402
from shared.logger import setup_logging  # noqa: E402

settings = get_settings()
setup_logging(settings.ENV, settings.LOG_DIR, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def _background_tasks():
    """Фоновые задачи: очистка expired-комнат, продление подписок."""
    from shared.models.game_room import GameRoomOrm
    from shared.models.subscription import SubscriptionOrm

    while True:
        try:
            rooms = await GameRoomOrm.expire_overdue()
            if rooms:
                logger.debug("Истёкших комнат очищено: %s", rooms)
            subs = await SubscriptionOrm.expire_overdue()
            if subs:
                logger.debug("Истёкших подписок: %s", subs)
        except Exception:
            logger.exception("Ошибка фоновой очистки")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_background_tasks())
    logger.info("FastAPI сервис запущен: %s:%s", settings.API_HOST, settings.API_PORT)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Bot Vasya API",
    description="REST API + WebApp для Telegram-бота Вася",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика WebApp
webapp_dir = Path(__file__).parent / "webapp"
static_dir = webapp_dir / "static" / "dist"
if not static_dir.exists():
    static_dir = webapp_dir / "static"
if static_dir.exists():
    app.mount("/webapp", StaticFiles(directory=str(static_dir), html=True), name="webapp")
    logger.info("WebApp-статика: %s", static_dir)
else:
    logger.warning("Папка WebApp-статики не найдена: %s", static_dir)


def register_routers() -> None:
    from src_fastapi.routes import payments, subscriptions, games, ads, user, admin

    app.include_router(payments.router)
    app.include_router(subscriptions.router)
    app.include_router(games.router)
    app.include_router(ads.router)
    app.include_router(user.router)
    app.include_router(admin.router)
    logger.info("API роутеры зарегистрированы")


register_routers()


@app.get("/")
async def root():
    return {"service": "bot_vasya_api", "status": "ok", "version": "2.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


def main() -> None:
    config = uvicorn.Config(
        app="src_fastapi.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
        reload=settings.ENV == "development",
    )
    server = uvicorn.Server(config)
    logger.info("Запуск Uvicorn на %s:%s", settings.API_HOST, settings.API_PORT)
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Остановка API...")
        sleep(1)


if __name__ == "__main__":
    main()
