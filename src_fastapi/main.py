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
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import get_settings  # noqa: E402
from shared.logger import setup_logging  # noqa: E402

settings = get_settings()
setup_logging(settings.ENV, settings.LOG_DIR, settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def _background_tasks():
    """Фоновые задачи: продление подписок, очистка комнат, expire."""
    from shared.models.game_room import GameRoomOrm
    from shared.models.subscription import SubscriptionOrm
    from shared.subscription_renewal import process_subscription_renewals

    while True:
        try:
            renew_stats = await process_subscription_renewals()
            if renew_stats.get("tried"):
                logger.info("Subscription renewals: %s", renew_stats)
            rooms = await GameRoomOrm.expire_overdue()
            if rooms:
                logger.debug("Просроченных комнат очищено: %s", rooms)
            subs = await SubscriptionOrm.expire_overdue()
            if subs:
                logger.debug("Просрочено подписок: %s", subs)
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


@app.middleware("http")
async def webapp_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/webapp/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/webapp/") and path.endswith((".js", ".css", ".woff2", ".png", ".svg")):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    elif path.startswith("/webapp/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response

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
    from src_fastapi.routes import payments, subscriptions, games, ads, user, admin, chats

    app.include_router(payments.router)
    app.include_router(subscriptions.router)
    app.include_router(games.router)
    app.include_router(ads.router)
    app.include_router(user.router)
    app.include_router(chats.router)
    app.include_router(admin.router)
    logger.info("API роутеры зарегистрированы")


register_routers()


def _landing_html() -> str:
    username = (settings.BOT_USERNAME or "").lstrip("@")
    bot_link = f"https://t.me/{username}" if username else "https://t.me/"
    bot_label = f"@{username}" if username else "бота Васю"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Вася — Telegram-бот для чатов</title>
  <style>
    :root {{
      --bg: #0b1020; --card: #141a2e; --text: #eef2ff; --muted: #9aa3bf;
      --accent: #7c5cff; --accent2: #22d3ee;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; font-family: Inter, system-ui, sans-serif;
      color: var(--text);
      background:
        radial-gradient(1200px 600px at 10% -10%, #2a1b6a 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #0e4b5c 0%, transparent 50%),
        var(--bg);
    }}
    .wrap {{ max-width: 720px; margin: 0 auto; padding: 48px 20px 64px; }}
    .card {{
      background: color-mix(in srgb, var(--card) 88%, transparent);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 24px; padding: 32px 28px; backdrop-filter: blur(10px);
      box-shadow: 0 20px 60px rgba(0,0,0,.35);
    }}
    .badge {{
      display: inline-block; font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
      color: var(--accent2); background: rgba(34,211,238,.12); border: 1px solid rgba(34,211,238,.25);
      padding: 6px 10px; border-radius: 999px; margin-bottom: 16px;
    }}
    h1 {{ margin: 0 0 12px; font-size: clamp(28px, 5vw, 40px); line-height: 1.15; }}
    p {{ margin: 0 0 14px; color: var(--muted); line-height: 1.6; font-size: 17px; }}
    ul {{ margin: 18px 0 24px; padding-left: 18px; color: var(--muted); }}
    li {{ margin: 8px 0; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }}
    a.btn {{
      display: inline-flex; align-items: center; justify-content: center; gap: 8px;
      text-decoration: none; border-radius: 14px; padding: 14px 18px; font-weight: 600;
    }}
    a.primary {{ background: linear-gradient(135deg, var(--accent), #4f46e5); color: white; }}
    a.ghost {{ background: rgba(255,255,255,.04); color: var(--text); border: 1px solid rgba(255,255,255,.1); }}
    .foot {{ margin-top: 22px; font-size: 13px; color: #6b728a; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="badge">Telegram-бот</div>
      <h1>Привет, я Вася</h1>
      <p>
        Разноображу ваш чат: болтаю по имени, мини-игры, профиль, подписки и WebApp прямо внутри Telegram.
      </p>
      <ul>
        <li>Отвечаю в группах, когда меня зовут</li>
        <li>Мини-игры: крестики-нолики, рулетка, слоты</li>
        <li>Профиль, донат и реклама через удобный WebApp</li>
      </ul>
      <div class="actions">
        <a class="btn primary" href="{bot_link}" target="_blank" rel="noopener">Открыть {bot_label} в Telegram</a>
</div>
      <p class="foot">
        Игровые комнаты и казино открываются только из Telegram. Если вы просто зашли на сайт — добавьте бота в чат и запускайте игры оттуда.
      </p>
    </div>
  </div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # JSON только по явному запросу (?format=json) или Accept: application/json
    accept = request.headers.get("accept", "")
    if request.query_params.get("format") == "json" or (
        "application/json" in accept and "text/html" not in accept
    ):
        return JSONResponse({"service": "bot_vasya_api", "status": "ok", "version": "2.0.0"})
    return HTMLResponse(_landing_html())




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
