from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from utils.filters import ChatTypeFilter
from utils.enums import ChatType
from .command import CommandStart

router = Router(name=__name__)
router.message.filter(
    ChatTypeFilter(
        ChatType.PRIVATE,
    )
)


@router.message(Command('ping'))
async def start(message: Message, bot: Bot):
    await bot(CommandStart(message.chat.id))
