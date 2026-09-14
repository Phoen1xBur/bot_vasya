"""Генерация текста: Markov chain + Mistral AI.

Markovify — для дешёвой генерации на основе истории сообщений чата.
Mistral (через shared.ai) — для AI-режима чата (когда включён).
"""

import logging
import random

import markovify

from shared.ai import chat_complete
from shared.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def generate_text(messages: list[str]) -> str:
    """Генерация текста цепью Маркова из истории чата."""
    if messages:
        text_model = markovify.NewlineText(
            "\n".join(messages), state_size=1, well_formed=False
        )
        msg_text = (
            text_model.make_short_sentence(max_chars=4096, tries=100)
            or random.choice(messages)
        )
        return msg_text
    return "У меня пока слишком мало информации о вас!!"


async def generate_text_from_ai(messages: list[dict[str, str]]) -> str:
    """AI-генерация ответа через Mistral."""
    if not messages:
        return "У меня пока слишком мало информации о вас!!"
    try:
        return await chat_complete(messages)
    except Exception:
        logger.exception("Ошибка AI-генерации")
        return generate_text([m.get("content", "") for m in messages if m.get("content")])
