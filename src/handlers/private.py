import logging
from urllib.parse import parse_qs

from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from keyboards.inline_kb_generate_start import build_inline_kb_start
from keyboards.inline_kb_webapp_casino import build_inline_kb_webapp_casino
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from run import logger
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
    logger = logging.getLogger(__name__)
    if command.args:
        try:
            params = parse_qs(command.args)
            # Логи в run.py, здесь оставим чистую обработку
            chat_id = params.get('chat_id', [None])[0]
            request_func = params.get('request_func', [None])[0]

            match request_func, chat_id:
                case 'profile', chat_id:
                    # Получаем данные профиля для конкретного чата
                    answer = await func.profile_for_chat(message.from_user.id, int(chat_id))
                    await message.answer(answer)
                case 'casino', chat_id:
                    await message.answer('Казино', reply_markup=build_inline_kb_webapp_casino())
                case 'minigame_ttt', chat_id:
                    # Кнопка для открытия WebApp игры TTT
                    webapp = WebAppInfo(url=f'https://vasyafun.ru/ttt?chat_id={chat_id}')
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Войти в игру', web_app=webapp)]])
                    await message.answer('Крестики-нолики: откройте WebApp', reply_markup=kb)
                case 'minigame_roulette', chat_id:
                    webapp = WebAppInfo(url=f'https://vasyafun.ru/roulette?chat_id={chat_id}')
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Войти в игру', web_app=webapp)]])
                    await message.answer('Казино — рулетка: откройте WebApp', reply_markup=kb)
                case _:
                    await message.answer(f'Неизвестная команда: {request_func}')

        except Exception as e:
            await message.answer('Ошибка обработки параметров запуска')
            logger.exception(f'Ошибка при отправке inline-клавиатуры со входом в WebApp. Описание ошибки: {e}')
    else:
        await bot(MyCommandStart(chat_id=message.chat.id))


@router.message(Command('profile_test'))
async def test_webapp(message: Message):
    inline_kb = await build_inline_kb_start(message.chat.id, 'profile', '📱 Открыть профиль')
    await message.answer('Быстрее смотри свой профиль!', reply_markup=inline_kb)
