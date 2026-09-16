"""Роуты подписок: информация и управление автопродлением."""

from fastapi import APIRouter, Depends, HTTPException

from shared.models.subscription import (
    SubscriptionOrm,
    TIER_AI_DAILY_LIMIT,
    TIER_FREE_JAIL_PER_DAY,
    TIER_LIMIT_MULTIPLIER,
    TIER_TAG,
    TIER_WORK_BONUS,
)
from shared.prices import get_tier_price_kopecks
from shared.enums import SubscriptionTier
from src_fastapi.deps import require_telegram_user

router = APIRouter(prefix="/api/subscriptions", tags=["Подписки"])


def _serialize(sub) -> dict:
    tier = sub.tier if sub else SubscriptionTier.FREE
    return {
        "tier": tier.value,
        "tag": TIER_TAG.get(tier, ""),
        "status": sub.status.value if sub else "none",
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "auto_renew": bool(sub.auto_renew) if sub else False,
        "has_recurring_key": bool(sub.recurring_key) if sub else False,
        "limits_multiplier": TIER_LIMIT_MULTIPLIER.get(tier, 1),
        "work_bonus": TIER_WORK_BONUS.get(tier, 0.0),
        "free_jail_per_day": TIER_FREE_JAIL_PER_DAY.get(tier, 0),
        "ai_daily_limit": TIER_AI_DAILY_LIMIT.get(tier, 0),
    }


@router.get("/me")
async def my_subscription(profile: dict = Depends(require_telegram_user)):
    """Текущая подписка пользователя."""
    sub = await SubscriptionOrm.get_active(profile["id"])
    return _serialize(sub)


@router.get("/plans")
async def subscription_plans():
    """Доступные тарифы (для отображения клиенту)."""
    plans = []
    for tier in [SubscriptionTier.VIP, SubscriptionTier.PREMIUM, SubscriptionTier.ELITE]:
        plans.append({
            "tier": tier.value,
            "tag": TIER_TAG.get(tier, ""),
            "price_kopecks": get_tier_price_kopecks(tier) or 0,
            "limits_multiplier": TIER_LIMIT_MULTIPLIER.get(tier, 1),
            "work_bonus": TIER_WORK_BONUS.get(tier, 0.0),
            "free_jail_per_day": TIER_FREE_JAIL_PER_DAY.get(tier, 0),
            "ai_daily_limit": TIER_AI_DAILY_LIMIT.get(tier, 0),
        })
    return {"plans": plans}


@router.post("/cancel_auto_renew")
async def cancel_auto_renew(profile: dict = Depends(require_telegram_user)):
    """Отключить автопродление одним кликом (текущий период догорает)."""
    ok = await SubscriptionOrm.cancel_auto_renew(profile["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Активная подписка не найдена")
    sub = await SubscriptionOrm.get_active(profile["id"])
    # get_active may still find it; also get_by_user for response
    if sub is None:
        sub = await SubscriptionOrm.get_by_user(profile["id"])
    return {"ok": True, "subscription": _serialize(sub) if sub else None}


@router.post("/resume_auto_renew")
async def resume_auto_renew(profile: dict = Depends(require_telegram_user)):
    """Включить автопродление, если карта уже привязана (есть RebillId)."""
    ok, reason = await SubscriptionOrm.enable_auto_renew(profile["id"])
    if not ok:
        if reason == "no_active":
            raise HTTPException(status_code=404, detail="Активная подписка не найдена")
        if reason == "no_rebill":
            raise HTTPException(
                status_code=400,
                detail="Карта не привязана. Оплатите подписку ещё раз — карта сохранится для автопродления.",
            )
        raise HTTPException(status_code=400, detail=reason)
    sub = await SubscriptionOrm.get_active(profile["id"])
    return {"ok": True, "subscription": _serialize(sub) if sub else None}
