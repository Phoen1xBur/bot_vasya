"""Единый AI-клиент (Mistral).

Используется в:
- AI-командах подписчиков (/ai_generate, /ai_roleplay)
- AI-проверке рекламы
- AI-благодарностях донатерам

Логирование всех запросов (контроль расходов). Лимиты по подписке.
"""

import json
import logging
from typing import Any

from mistralai.client import Mistral
from mistralai.client.models import ChatCompletionResponse

from shared.config import get_settings
from shared.enums import SubscriptionTier
from shared.models.subscription import SubscriptionOrm, TIER_AI_DAILY_LIMIT

logger = logging.getLogger(__name__)
_ai_logger = logging.getLogger("ai_requests")

_settings = get_settings()
_mistral: Mistral | None = None


def get_mistral() -> Mistral:
    global _mistral
    if _mistral is None:
        _mistral = Mistral(api_key=_settings.AI_API_KEY)
    return _mistral


async def get_user_tier(user_id: int) -> SubscriptionTier:
    sub = await SubscriptionOrm.get_active(user_id)
    return sub.tier if sub else SubscriptionTier.FREE


def _daily_ai_key(user_id: int) -> str:
    from datetime import date

    import redis as redis_package

    r = redis_package.Redis(**_settings.REDIS_CREDENTIALS)
    key = f"ai:usage:{user_id}:{date.today().isoformat()}"
    return key, r


async def check_ai_limit(user_id: int, tier: SubscriptionTier) -> bool:
    """Проверка дневного лимита AI-запросов. Возвращает True если можно."""
    limit = TIER_AI_DAILY_LIMIT.get(tier, 0)
    if limit == -1:  # безлимит
        return True
    if limit == 0:
        return False
    key, r = _daily_ai_key(user_id)
    try:
        current = int(r.get(key) or 0)
        return current < limit
    except Exception:
        return True  # Redis упал — даём попробовать


async def increment_ai_usage(user_id: int) -> None:
    key, r = _daily_ai_key(user_id)
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)  # сутки
        pipe.execute()
    except Exception:
        logger.warning("Не удалось инкрементировать AI-счётчик", exc_info=True)


async def get_ai_usage(user_id: int) -> int:
    key, r = _daily_ai_key(user_id)
    try:
        return int(r.get(key) or 0)
    except Exception:
        return 0


async def chat_complete(
    messages: list[dict[str, str]],
    model: str | None = None,
    user_id: int | None = None,
) -> str:
    """Запрос к Mistral chat. Возвращает текст ответа."""
    mistral = get_mistral()
    model = model or _settings.AI_MODEL
    try:
        response: ChatCompletionResponse = await mistral.chat.complete_async(
            model=model, messages=messages
        )
        text = response.choices[0].message.content
        _ai_logger.info(
            "AI chat request user_id=%s model=%s tokens=%s",
            user_id,
            model,
            getattr(response.usage, "total_tokens", "?") if response.usage else "?",
        )
        return text
    except Exception:
        logger.exception("Ошибка AI-запроса (chat)")
        raise


# ---------------- AI-команды для подписчиков ----------------


async def ai_generate_text(user_id: int, prompt: str) -> str:
    """Генерация текста/истории/шутки."""
    messages = [
        {"role": "system", "content": "Ты — креативный ассистент бота Васи. Генерируешь короткие весёлые тексты на русском."},
        {"role": "user", "content": prompt},
    ]
    return await chat_complete(messages, user_id=user_id)


async def ai_roleplay(user_id: int, prompt: str) -> str:
    """Ролевая игра."""
    messages = [
        {"role": "system", "content": "Ты — ролевой ассистент. Отвечай в стиле короткой ролевой сцены на русском."},
        {"role": "user", "content": prompt},
    ]
    return await chat_complete(messages, user_id=user_id)


# ---------------- AI-проверка рекламы ----------------


async def ai_check_ad(text: str, rules: list[str]) -> dict[str, Any]:
    """Проверка рекламного текста на соответствие правилам.

    Возвращает строго JSON: {"approved": bool, "reason": str, "risk_level": str}
    """
    rules_block = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rules))
    prompt = (
        "Проверь рекламное сообщение на соответствие правилам ниже. "
        "Ответь СТРОГО валидным JSON без markdown: "
        '{"approved": true/false, "reason": "краткое объяснение", "risk_level": "low/medium/high"}\n\n'
        f"Правила:\n{rules_block}\n\n"
        f"Рекламный текст:\n{text}"
    )
    messages = [
        {"role": "system", "content": "Ты — модератор рекламы. Отвечаешь только валидным JSON."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await chat_complete(messages)
        # Извлекаем JSON (может быть с мусором по краям)
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
        verdict = json.loads(raw)
        if not isinstance(verdict, dict):
            return {"approved": False, "reason": "Некорректный ответ AI", "risk_level": "medium"}
        verdict.setdefault("approved", False)
        verdict.setdefault("reason", "")
        verdict.setdefault("risk_level", "medium")
        return verdict
    except Exception:
        logger.exception("Ошибка AI-проверки рекламы")
        return {"approved": False, "reason": "Ошибка AI-проверки", "risk_level": "medium"}


# ---------------- AI-благодарность донатерам ----------------


async def ai_thank_donor(user_id: int, amount: int) -> str:
    messages = [
        {"role": "system", "content": "Ты — бот Вася. Поблагодари донатера тёплым коротким сообщением на русском."},
        {"role": "user", "content": f"Пользователь задонатил {amount} рублей. Поблагодари его."},
    ]
    try:
        return await chat_complete(messages, user_id=user_id)
    except Exception:
        return "Спасибо за поддержку проекта! ❤️"
