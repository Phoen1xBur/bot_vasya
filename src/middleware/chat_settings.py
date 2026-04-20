from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from models import TelegramChatOrm


class ChatSettingsMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
    ):
        try:
            if event and event.chat and event.chat.id:
                data["chat_settings"]: TelegramChatOrm = await TelegramChatOrm.get_telegram_chat(event.chat.id)
        except:
            pass
        finally:
            return await handler(event, data)
