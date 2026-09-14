from aiogram import F, Router
from aiogram.types import Message

from shared.config import get_settings
from utils.filters import ChatTypeFilter
from shared.enums import ChatType
from utils.stt import transcribe

router = Router(name=__name__)
router.message.filter(ChatTypeFilter(ChatType.GROUP, ChatType.SUPERGROUP))

_settings = get_settings()


@router.message(F.voice | F.audio)
async def handle_voice(message: Message):
    """Распознавание голосовых через Vosk (если включён)."""
    if not _settings.VOSK_ENABLED:
        return
    try:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await message.bot.get_file(file_id)
        import os
        import tempfile

        # Скачиваем
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await message.bot.download_file(file.file_path, tmp.name)
            text = await transcribe(tmp.name)
            os.unlink(tmp.name)
        if text:
            await message.reply(f"🎙 Распознано: {text}")
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Ошибка распознавания голоса")
