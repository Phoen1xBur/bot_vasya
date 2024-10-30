from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.filters import ChatTypeFilter
from utils.enums import ChatType

router = Router(name=__name__)
router.message.filter(
    ChatTypeFilter(
        ChatType.PRIVATE,
    )
)


@router.message(Command('ping'))
async def start(message: Message):
    await message.answer('pong!')
