"""Speech-to-text через Vosk.

Улучшения:
- Асинхронная загрузка модели (не блокирует event loop).
- Распознавание через asyncio.to_thread.
- Graceful disable если модель не найдена (VOSK_ENABLED=false).
Готова к запуску на мощном сервере.
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Optional

from shared.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

# Глобальный экземпляр (загружается лениво)
_stt_instance: Optional["STT"] = None
_stt_lock = asyncio.Lock()


class STT:
    def __init__(self, model_path: str | None = None, sample_rate: int = 16000) -> None:
        self.model_path = model_path or _settings.VOSK_MODEL_PATH
        self.sample_rate = sample_rate
        self._model = None
        self._available = False
        self._load_model()

    def _load_model(self) -> None:
        if not _settings.VOSK_ENABLED:
            logger.info("Vosk отключён (VOSK_ENABLED=false)")
            return
        if not os.path.exists(self.model_path):
            logger.warning(
                "Vosk модель не найдена: %s. Распознавание голоса отключено. "
                "Скачайте модель: https://alphacephei.com/vosk/models",
                self.model_path,
            )
            return
        try:
            from vosk import KaldiRecognizer, Model

            self._model = Model(self.model_path)
            self._recognizer = KaldiRecognizer(self._model, self.sample_rate)
            self._recognizer.SetWords(True)
            self._available = True
            logger.info("Vosk модель загружена: %s", self.model_path)
        except Exception:
            logger.exception("Ошибка загрузки Vosk модели")

    @property
    def available(self) -> bool:
        return self._available

    def _recognize_sync(self, audio_file_name: str) -> str:
        """Синхронное распознавание (запускается в потоке через to_thread)."""
        # Конвертация в wav через ffmpeg
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-loglevel", "quiet",
                "-i", audio_file_name,
                "-ar", str(self.sample_rate),
                "-ac", "1",
                "-f", "s16le",
                "-",
            ],
            stdout=subprocess.PIPE,
        )
        while True:
            data = process.stdout.read(4000)
            if len(data) == 0:
                break
            if self._recognizer.AcceptWaveform(data):
                pass
        result_json = self._recognizer.FinalResult()
        result_dict = json.loads(result_json)
        return result_dict.get("text", "")

    async def audio_to_text(self, audio_file_name: str) -> str:
        """Асинхронное распознавание — не блокирует event loop."""
        if not self._available:
            return ""
        if not os.path.exists(audio_file_name):
            return ""
        return await asyncio.to_thread(self._recognize_sync, audio_file_name)


async def get_stt() -> Optional[STT]:
    """Получить синглтон STT (ленивая инициализация)."""
    global _stt_instance
    if _stt_instance is not None:
        return _stt_instance
    async with _stt_lock:
        if _stt_instance is None:
            _stt_instance = STT()
    return _stt_instance


async def transcribe(audio_file_name: str) -> str:
    """Распознать аудио в текст. Возвращает '' если Vosk недоступен."""
    stt = await get_stt()
    if stt is None or not stt.available:
        return ""
    return await stt.audio_to_text(audio_file_name)
