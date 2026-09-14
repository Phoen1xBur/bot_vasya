"""Роутер подписок: информация о подписке пользователя."""

from fastapi import APIRouter, Depends

from shared.models.subscription import (
    SubscriptionOrm,
    TIER_AI_DAILY_LIMIT,
    TIER_FREE_JAIL_PER_DAY,
    TIER_LIMIT_MULTIPLIER,
    TIER_PRICES_KOPECKS,
    TIER_TAG,
    TIER_WORK_BONUS,
)
from shared.enums import SubscriptionTier
from src_fastapi.deps import require_telegram_user

router = APIRouter(prefix="/api/subscriptions", tags=["Подписки"])


@router.get("/me")
async def my_subscription(profile: dict = Depends(require_telegram_user)):
    """Текущая подписка пользователя."""
    sub = await SubscriptionOrm.get_active(profile["id"])
    tier = sub.tier if sub else SubscriptionTier.FREE
    return {
        "tier": tier.value,
        "tag": TIER_TAG.get(tier, ""),
        "status": sub.status.value if sub else "none",
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "auto_renew": sub.auto_renew if sub else False,
        "limits_multiplier": TIER_LIMIT_MULTIPLIER.get(tier, 1),
        "work_bonus": TIER_WORK_BONUS.get(tier, 0.0),
        "free_jail_per_day": TIER_FREE_JAIL_PER_DAY.get(tier, 0),
        "ai_daily_limit": TIER_AI_DAILY_LIMIT.get(tier, 0),
    }


@router.get("/plans")
async def subscription_plans():
    """Доступные тарифы (для страницы оплаты)."""
    plans = []
    for tier in [SubscriptionTier.VIP, SubscriptionTier.PREMIUM, SubscriptionTier.ELITE]:
        plans.append({
            "tier": tier.value,
            "tag": TIER_TAG.get(tier, ""),
            "price_kopecks": TIER_PRICES_KOPECKS.get(tier, 0),
            "limits_multiplier": TIER_LIMIT_MULTIPLIER.get(tier, 1),
            "work_bonus": TIER_WORK_BONUS.get(tier, 0.0),
            "free_jail_per_day": TIER_FREE_JAIL_PER_DAY.get(tier, 0),
            "ai_daily_limit": TIER_AI_DAILY_LIMIT.get(tier, 0),
        })
    return {"plans": plans}
