from aiogram import Router, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .command import CommandStart, CommandHelp

router = Router(name=__name__)


@router.message(Command('start'))
async def start(message: Message, bot: Bot):
    await bot(CommandStart(chat_id=message.chat.id))


@router.message(Command('help'))
async def get_help(message, bot: Bot):
    await bot(CommandHelp(chat_id=message.chat.id))
