from urllib.parse import parse_qs

from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from keyboards.webapp_test import *
from utils.filters import ChatTypeFilter
from utils.enums import ChatType
from . import func
from .command import CommandStart as MyCommandStart

router = Router(name=__name__)
router.message.filter(
    ChatTypeFilter(
        ChatType.PRIVATE,
    )
)


@router.message(CommandStart(deep_link=True, deep_link_encoded=True))
async def start(message: Message, command: CommandObject, bot: Bot):
    if command.args:
        try:
            params = parse_qs(command.args)
            chat_id = params.get('chat_id', [None])[0]
            request_func = params.get('request_func', [None])[0]

            if request_func == 'profile' and chat_id:
                # Получаем данные профиля для конкретного чата
                answer = await func.profile_for_chat(message.from_user.id, int(chat_id))
                await message.answer(answer)
                return

        except Exception as e:
            print(f"Error parsing start params: {e}")
    else:
        await bot(MyCommandStart(chat_id=message.chat.id))


@router.message(Command('profile_test'))
async def test_webapp(message: Message):
    inline_kb = await build_inline_kb_start(message.chat.id, 'profile')
    await message.answer('Быстрее смотри свой профиль!', reply_markup=inline_kb)
