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


def _norm(s: str) -> str:
    return " ".join((s or "").casefold().split())


def generate_text(messages: list[str]) -> str | None:
    """Генерация текста цепью Маркова из истории чата.

    Never returns an exact past message (that caused joke spam).
    Returns None if generation failed / would be a duplicate.
    """
    corpus = [m for m in messages if (m or "").strip()]
    if not corpus:
        return None
    seen = {_norm(m) for m in corpus[-80:]}
    text_model = markovify.NewlineText(
        "\n".join(corpus), state_size=1, well_formed=False
    )
    for _ in range(12):
        msg_text = text_model.make_short_sentence(max_chars=280, tries=50)
        if not msg_text:
            continue
        if _norm(msg_text) in seen:
            continue
        if len(msg_text.strip()) < 8:
            continue
        return msg_text
    return None



async def generate_text_from_ai(messages: list[dict[str, str]]) -> str:
    """AI-генерация ответа через Mistral."""
    if not messages:
        return "У меня пока слишком мало информации о вас!!"
    try:
        return await chat_complete(messages)
    except Exception:
        logger.exception("Ошибка AI-генерации")
        fallback = generate_text([m.get("content", "") for m in messages if m.get("content")])
        return fallback or "Не смог придумать ответ, попробуйте ещё раз."
