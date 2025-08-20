import os
from pathlib import Path

import aiogram
from aiogram import Router
from aiogram.types import Message

from utils.stt import STT
from . import func
from utils.filters import ChatTypeFilter, MessageTypeFilter
from utils.enums import ChatType, ContentType

from config import settings

router = Router(name=__name__)
router.message.filter(
    # События только из:
    # Тип чата: группа/супергруппа
    ChatTypeFilter(
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ),
    # Тип сообщения: Голосовое
    MessageTypeFilter(
        ContentType.VOICE,
    ),
    # Пока не работает: TypeError: unsupported callable
    # Сообщение сгенерированное НЕ ботом
    # not F.via_bot,
    # Тип пересылки сообщения: Отсутствует
    # F.forward_origin is None
)

stt = None
if settings.ENABLE_VOICE:
    stt = STT()


@router.message()
async def groups_voice(message: Message, bot: aiogram.Bot):
    """
    Обработка голосовых сообщений в группах, возвращение расшифровки голоса
    """
    if not stt:
        return
    # Получаем голосовое сообщение
    voice = message.voice
    if not voice:
        return
    # Проверяем длительность, если больше 3мин., то не обрабатываем
    if voice.duration > 60 * 3:
        return

    # Получаем файл голосового сообщения
    file = await bot.get_file(message.voice.file_id)
    file_path = file.file_path
    file_on_disk = Path('', f'{message.voice.file_id}.tmp')
    await bot.download_file(file_path, destination=file_on_disk)

    # Расшифровываем голос в текст
    try:
        text = stt.audio_to_text(file_on_disk)
        print(f'{text=}')
    finally:
        os.remove(file_on_disk)

    if not text:
        return
    await message.reply('Расшифровка текста:\n' + aiogram.html.quote(text))
