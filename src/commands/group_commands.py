from aiogram import Bot
from aiogram.types import Message

from shared.enums import SubscriptionTier
from shared.models.chat import TelegramChatOrm
from utils.auto_delete_message_service import AutoDeleteService
from .base import BotCommand, CommandResult
from handlers import func


class WorkCommand(BotCommand):
    async def execute(
        self,
        message: Message,
        bot: Bot,
        message_delete_service: AutoDeleteService,
        chat_settings: TelegramChatOrm | None = None,
        sub_tier: SubscriptionTier = SubscriptionTier.FREE,
        *args,
        **kwargs,
    ) -> CommandResult:
        answer = await func.work(message, sub_tier)
        message_answer = await message.answer(answer)
        message_delete_service.schedule(message.chat.id, message.message_id)
        message_delete_service.schedule(message_answer.chat.id, message_answer.message_id)
        return CommandResult(text=answer)

    @property
    def names(self) -> tuple[str, ...]:
        return "работа", "работать"
