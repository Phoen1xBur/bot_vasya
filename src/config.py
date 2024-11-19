from pydantic_settings import BaseSettings, SettingsConfigDict
from aiogram.types import BotCommand
import redis as redis_package

# https://core.telegram.org/bots/api#html-style
help_text = """<b>Список команд:</b>

<b>• Вася шанс [от 0 до 100] —</b> изменит шанс отправки сообщения

<b>• Вася выбери [значение 1 или значение 2] —</b> выберет одно из предложенного 

<b>• Вася кот —</b> отправит картинку  котика

<b>• Вася кот [текст сообщения] —</b>  отправит картинку котика с текстом

<b>• Вася ответь [текст сообщения] / Вася ответь гиф [текст сообщения] ——</b> ответит да/нет с гифкой или без 

<b>• Вася кто [текст] —</b> выберет рандомного участника чата"""


class Settings(BaseSettings):
    TOKEN: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    API_ID: str
    API_HASH: str
    REDIS_HOST: str
    REDIS_PORT: int

    @property
    def BOT_NAMES(self) -> tuple:
        return 'вася', 'вачя', 'васч', 'василий'
        # return 'вв', 'в'

    @property
    def MY_COMMANDS(self) -> list[BotCommand]:
        commands = [
            BotCommand(command="start", description="Старт"),
            BotCommand(command="help", description="Помощь по боту"),
            BotCommand(command="work", description="Время работать и зарабатывать!"),
            BotCommand(command="profile", description="Информация о твоем профиле"),
            # BotCommand(command="rob", description="Кража! Укради у ближнего своего"),
        ]
        return commands

    @property
    def DATABASE_URL_asyncpg(self) -> str:
        # DSN
        # postgresql+ascyncpg://user:pass@host:port/dbname
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_psycopg(self) -> str:
        # DSN
        # postgresql+psycopg://user:pass@host:port/dbname
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file='.env')


settings = Settings()
redis = redis_package.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
