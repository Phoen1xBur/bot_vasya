# run.py
import asyncio
import uvicorn

from aiogram import Bot, Dispatcher
from pyrogram import Client
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from config import settings

"""Fix utils"""
from utils.fix.fix_pyrogram import *  # noqa

"""End fix"""

# Инициализация бота и клиента
bot = Bot(token=settings.TOKEN)
dp = Dispatcher()

app = Client(
    'vasya_fun_bot',
    settings.API_ID,
    settings.API_HASH
)

# Инициализация FastAPI
fastapi_app = FastAPI(title="Telegram Bot WebApp API")

# Добавляем CORS middleware
from fastapi.middleware.cors import CORSMiddleware

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статику для WebApp
webapp_static_path = os.path.join(os.path.dirname(__file__), "src", "webapp", "static")
if os.path.exists(webapp_static_path):
    fastapi_app.mount("/webapp", StaticFiles(directory=webapp_static_path, html=True), name="webapp")


async def start_bot():
    """Запуск Telegram бота"""
    from handlers import routers

    dp.include_routers(*routers)
    await bot.set_my_commands(settings.MY_COMMANDS)
    bot.default.parse_mode = 'HTML'

    # Запуск polling
    await dp.start_polling(bot)


async def start_fastapi():
    """Запуск FastAPI сервера"""
    # Импортируем и подключаем роуты
    try:
        from src.api.routes import games, calendar, user
        fastapi_app.include_router(user.router, prefix="/api/user", tags=["user"])
        fastapi_app.include_router(games.router, prefix="/api/games", tags=["games"])
        fastapi_app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
    except ImportError as e:
        print(f"Warning: Could not import API routes: {e}")

    config = uvicorn.Config(
        app=fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def on_startup():
    """Запуск всех сервисов"""
    # Создаем задачи для бота и API
    bot_task = asyncio.create_task(start_bot())
    api_task = asyncio.create_task(start_fastapi())

    # Ждем завершения обеих задач
    await asyncio.gather(bot_task, api_task)


if __name__ == '__main__':
    try:
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        print('Stopping...')
    except Exception as e:
        print(f'Error: {e}')
