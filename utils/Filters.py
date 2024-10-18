from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_type: Union[str, list]):
        self.chat_type = chat_type

    async def __call__(self, message: Message) -> bool:
        if isinstance(self.chat_type, str):
            return message.chat.type == self.chat_type
        else:
            return message.chat.type in self.chat_type


class BotNameFilter(BaseFilter):
    def __init__(self, bot_names: Union[str, tuple]):
        self.bot_names = bot_names

    async def __call__(self, message: Message) -> bool:
        try:
            return message.text.lower().split()[0] in self.bot_names
        except IndexError:
            return False
        except AttributeError:
            return False
