"""Middleware: теги подписки [VIP]/[Premium]/[Elite] во ВСЕХ чатах.

Подписка привязана к Telegram user_id (не к чату).
Статус тянет из БД, кэш в Redis на 5 минут.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from shared.enums import SubscriptionTier
from shared.models.subscription import SubscriptionOrm, TIER_TAG
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
CACHE_TTL = 300  # 5 минут


class SubscriptionTagsMiddleware(BaseMiddleware):
    """Инжектит tier и тег подписки в data['sub_tier'] и data['sub_tag']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        tier = SubscriptionTier.FREE
        tag = ""
        if user and getattr(user, "id", None):
            user_id = user.id
            try:
                r = get_redis()
                cache_key = f"sub:tier:{user_id}"
                cached = r.get(cache_key)
                if cached:
                    tier = SubscriptionTier(cached)
                else:
                    sub = await SubscriptionOrm.get_active(user_id)
                    tier = sub.tier if sub else SubscriptionTier.FREE
                    r.set(cache_key, tier.value, ex=CACHE_TTL)
                tag = TIER_TAG.get(tier, "")
            except Exception:
                logger.debug("Не удалось загрузить подписку user=%s", user_id, exc_info=True)

        data["sub_tier"] = tier
        data["sub_tag"] = tag
        return await handler(event, data)
