from pydantic_settings import BaseSettings, SettingsConfigDict
from aiogram.types import BotCommand


class Settings(BaseSettings):
    TOKEN: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASS: str

    @property
    def BOT_NAMES(self) -> tuple:
        return 'вася', 'вачя'

    @property
    def MY_COMMANDS(self) -> list[BotCommand]:
        commands = [
            BotCommand(command="start", description="Start bot"),
            BotCommand(command="help", description="Help menu"),
            BotCommand(command="another", description="Another command"),
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
