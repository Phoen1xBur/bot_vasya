import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject, Update

from models.chat import TelegramChatOrm

logger = logging.getLogger(__name__)


def _extract_chat(event: TelegramObject) -> Optional[Chat]:
    if isinstance(event, Message):
        return event.chat
    if isinstance(event, CallbackQuery):
        if event.message and isinstance(event.message, Message):
            return event.message.chat
        return None
    if isinstance(event, Update):
        for attr in (
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "callback_query",
        ):
            nested = getattr(event, attr, None)
            if nested is None:
                continue
            chat = _extract_chat(nested)
            if chat is not None:
                return chat
    return getattr(event, "chat", None)


class ChatSettingsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Always inject so aiogram DI does not raise TypeError on handlers
        data["chat_settings"] = None

        chat = _extract_chat(event)
        if chat is None:
            return await handler(event, data)

        try:
            chat_settings = await TelegramChatOrm.get_telegram_chat(chat.id)
            if chat_settings is None:
                await TelegramChatOrm.insert_or_update_telegram_chat(chat_id=chat.id)
                chat_settings = await TelegramChatOrm.get_telegram_chat(chat.id)
            data["chat_settings"] = chat_settings
        except Exception:
            logger.exception(
                "Failed to load chat_settings for chat_id=%s", getattr(chat, "id", None)
            )

        return await handler(event, data)
