from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


router = Router(name=__name__)


# https://core.telegram.org/bots/api#html-style
help_text = """<b>Список команд:</b>

<b>• Вася шанс [от 0 до 100] —</b> изменит шанс отправки сообщения

<b>• Вася выбери [значение 1 или значение 2] —</b> выберет одно из предложенного 

<b>• Вася кот —</b> отправит картинку  котика

<b>• Вася кот [текст сообщения] —</b>  отправит картинку котика с текстом

<b>• Вася ответь [текст сообщения] / Вася ответь гиф [текст сообщения] ——</b> ответит да/нет с гифкой или без 

<b>• Вася кто [текст] —</b> выберет рандомного участника чата"""


@router.message(Command('start'))
async def start(message: Message):
    await message.answer('Привет!')


@router.message(Command('help'))
async def get_help(message):
    await message.answer(help_text)
