from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message

from utils.enums import ChatType, ContentType


class ChatTypeFilter(BaseFilter):
    def __init__(self, *chat_type: Union[ChatType, list[ChatType]]):
        self.chat_type = chat_type

    async def __call__(self, message: Message) -> bool:
        if isinstance(self.chat_type, ChatType):
            return message.chat.type == self.chat_type
        else:
            return message.chat.type in self.chat_type


class MessageTypeFilter(BaseFilter):
    def __init__(self, *message_type: Union[ContentType, list[ContentType]]):
        self.message_type = message_type

    async def __call__(self, message: Message) -> bool:
        if isinstance(self.message_type, ContentType):
            return message.content_type == self.message_type
        else:
            return message.content_type in self.message_type


class BotNameFilter(BaseFilter):
    def __init__(self, bot_names: Union[str, tuple]):
        self.bot_names = bot_names

    async def __call__(self, message: Message) -> bool:
        try:
            return message.text.casefold().split()[0] in self.bot_names
        except IndexError:
            return False
        except AttributeError:
            return False
