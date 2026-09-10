from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message, ReplyMarkupUnion

from models import TelegramChatOrm
from utils.auto_delete_message_service import AutoDeleteService


@dataclass
class CommandResult:
    text: str | None = None
    animation: str | None = None
    reply_markup: ReplyMarkupUnion | None = None
    need_delete_this_message: bool = False


class BotCommand(ABC):
    @abstractmethod
    async def execute(
            self,
            message: Message,
            bot: Bot,
            message_delete_service: AutoDeleteService,
            chat_settings: TelegramChatOrm,
            *args,
            **kwargs
    ) -> CommandResult:
        raise NotImplementedError()

    @property
    @abstractmethod
    def names(self) -> tuple[str, ...]:
        """Возвращает список имен (алиасов) названия команды"""
        raise NotImplementedError()

    @property
    def admin_only(self) -> bool:
        return False