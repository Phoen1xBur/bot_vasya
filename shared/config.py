"""Единая конфигурация для обоих сервисов (бот + API).

Секреты — только из переменных окружения / .env. Никаких хардкодов.
"""

import json
from functools import lru_cache

from aiogram.types import BotCommand
from pydantic_settings import BaseSettings, SettingsConfigDict


# https://core.telegram.org/bots/api#html-style
HELP_TEXT = """<b>Список команд:</b>

<b>• Вася профиль —</b> покажет статистику пользователя

<b>• Вася шанс [от 0 до 100] —</b> изменит шанс отправки сообщения

<b>• Вася выбери [значение 1 или значение 2] —</b> выберет одно из предложенного

<b>• Вася кот / Вася кот [текст сообщения] —</b> отправит картинку котика

<b>• Вася ответь [текст] / Вася ответь гиф [текст] —</b> ответит да/нет

<b>• Вася кто [текст] —</b> выберет рандомного участника чата

<b>• Вася убить [@пользователь] —</b> «убьёт» участника

<b>• Вася перевод [сумма] [@пользователь] —</b> перевод суммы

<b>• Вася работа —</b> устроит на рандомную работу

<b>• Вася кража [@пользователь] —</b> кража денег с баланса

<b>• Вася топ —</b> топ-10 участников чата по деньгам

<b>Платные (подписка):</b>
<b>• /subscribe —</b> оформить VIP/Premium/Elite
<b>• /unsubscribe —</b> отключить автопродление
<b>• /free —</b> досрочный выход из тюрьмы (для подписчиков)
<b>• /ai_generate —</b> AI-генерация текста
<b>• /ai_roleplay —</b> ролевая игра с AI

<b>Поддержка:</b>
<b>• /donate —</b> поддержать проект
<b>• /advertise —</b> подать рекламу
"""


class Settings(BaseSettings):
    # --- Telegram ---
    TOKEN: str
    API_ID: str = ""
    API_HASH: str = ""
    # Публичный @username без @ (для лендинга и ссылок t.me)
    BOT_USERNAME: str = ""

    # --- БД ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "bot_vasya"
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    # Полный URL переопределяет assembled-URL (для тестов на SQLite:
    # DATABASE_URL=sqlite+aiosqlite:///:memory:, DATABASE_URL_SYNC=sqlite:///:memory:).
    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    # --- AI (Mistral) ---
    AI_API_KEY: str = ""
    AI_MODEL: str = "mistral-medium-latest"

    # --- Vosk (speech-to-text) ---
    VOSK_ENABLED: bool = False
    VOSK_MODEL_PATH: str = "src/utils/models/vosk/vosk-model-ru-0.42"

    # --- T-Bank Acquiring ---
    # Достаточно WEBAPP_BASE_URL: Success/Fail/Notification собираются сами.
    # Эти три поля — только ручной override (оставьте пустыми в обычном случае).
    TBANK_TERMINAL_ID: str = ""
    TBANK_TERMINAL_PASSWORD: str = ""
    TBANK_SUCCESS_URL: str = ""
    TBANK_FAIL_URL: str = ""
    TBANK_NOTIFICATION_URL: str = ""
    # На серверах с корпоративным/self-signed MITM в цепочке — False
    TBANK_SSL_VERIFY: bool = True

    # --- Админы (массив Telegram user_id) ---
    ADMIN_IDS: str = "[]"

    # --- Игры ---
    GAME_ROOM_TTL_MINUTES: int = 15
    GAME_COMMISSION_PERCENT: int = 10  # комиссия бота со ставок
    GAME_ROULETTE_MAX_PLAYERS: int = 8

    # --- Лимиты экономики (бесплатно) ---
    WORK_COOLDOWN_MINUTES: int = 60
    ROB_COOLDOWN_MINUTES: int = 360
    PRISON_HOURS: int = 2

    # --- API / WebApp ---
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    WEBAPP_BASE_URL: str = "http://127.0.0.1:8000"  # публичный URL WebApp
    CORS_ORIGINS: str = "*"

    # --- Шина сообщений (RabbitMQ) ---
    RABBITMQ_URL: str = "amqp://guest:guest@127.0.0.1/"
    RABBITMQ_EXCHANGE: str = "vasya.bus"

    # --- Логирование/конфиг ---
    ENV: str = "development"  # development | production
    LOG_DIR: str = "logs"
    LOG_LEVEL: str | None = None

    # Совместимость со старым именом
    @property
    def MISTRAL_API_KEY(self) -> str:
        return self.AI_API_KEY

    @property
    def MISTRAL_MODEL(self) -> str:
        return self.AI_MODEL

    @property
    def BOT_NAMES(self) -> tuple:
        return "вася", "вачя", "васч", "василий", "vasya"

    @property
    def ADMIN_ID_SET(self) -> set[int]:
        try:
            ids = json.loads(self.ADMIN_IDS)
            return {int(x) for x in ids}
        except Exception:
            return set()

    @property
    def MY_COMMANDS(self) -> list[BotCommand]:
        return [
            BotCommand(command="start", description="Старт"),
            BotCommand(command="help", description="Помощь по боту"),
            BotCommand(command="work", description="Работать и зарабатывать!"),
            BotCommand(command="profile", description="Твой профиль"),
            BotCommand(command="top_users", description="Топ по деньгам"),
            BotCommand(command="minigames", description="Мини-игры"),
            BotCommand(command="subscribe", description="Подписка VIP/Premium/Elite"),
            BotCommand(command="donate", description="Поддержать проект"),
            BotCommand(command="advertise", description="Подать рекламу"),
        ]


    @property
    def tbank_success_url(self) -> str:
        """Куда банк вернёт пользователя после успешной оплаты (страница WebApp)."""
        if self.TBANK_SUCCESS_URL:
            return self.TBANK_SUCCESS_URL
        base = self.WEBAPP_BASE_URL.rstrip("/")
        return f"{base}/webapp/index.html?page=payment&status=success"

    @property
    def tbank_fail_url(self) -> str:
        """Куда банк вернёт пользователя после неуспешной оплаты."""
        if self.TBANK_FAIL_URL:
            return self.TBANK_FAIL_URL
        base = self.WEBAPP_BASE_URL.rstrip("/")
        return f"{base}/webapp/index.html?page=payment&status=fail"

    @property
    def tbank_notification_url(self) -> str:
        """Серверный webhook банка (не страница для человека)."""
        if self.TBANK_NOTIFICATION_URL:
            return self.TBANK_NOTIFICATION_URL
        base = self.WEBAPP_BASE_URL.rstrip("/")
        return f"{base}/api/payments/webhook"

    @property
    def DATABASE_URL_asyncpg(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_psycopg(self) -> str:
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_CREDENTIALS(self) -> dict:
        creds = {
            "host": self.REDIS_HOST,
            "port": self.REDIS_PORT,
            "db": self.REDIS_DB,
            "decode_responses": True,
        }
        if self.REDIS_PASSWORD:
            creds["password"] = self.REDIS_PASSWORD
        return creds

    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
