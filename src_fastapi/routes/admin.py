"""Роутер админ-панели: статистика, управление, цены.

Доступ: только админы (require_admin_user). Авторизация через initData (HMAC).
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from shared.config import get_settings
from shared.enums import AdCampaignStatus, PaymentStatus, SubscriptionTier
from shared.economy import balance_report
from shared.models.ad_campaign import AdCampaignOrm
from shared.models.donation import DonationOrm
from shared.models.payment import PaymentOrm
from shared.models.subscription import (
    SubscriptionOrm,
    TIER_PRICES_KOPECKS,
)
from shared.redis_client import get_redis
from src_fastapi.deps import require_admin_user

logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["Админ-панель"])

# Кэш цен в Redis (настраиваемые)
PRICE_KEYS = {
    "sub_vip": "price:sub:vip",
    "sub_premium": "price:sub:premium",
    "sub_elite": "price:sub:elite",
    "ad_per_1000": "price:ad:per_1000",
    "ai_check_enabled": "config:ad:ai_check",
}


@router.get("/stats")
async def get_stats(profile: dict = Depends(require_admin_user)):
    """Сводная статистика."""
    # Доход
    from sqlalchemy import select, func
    from shared.database import async_session_factory
    from shared.models.payment import PaymentOrm as P
    from shared.models.subscription import SubscriptionOrm as S
    from shared.models.ad_campaign import AdCampaignOrm as A

    async with async_session_factory() as session:
        # Сумма подтверждённых платежей
        rev_result = await session.execute(
            select(func.coalesce(func.sum(P.amount), 0)).filter(
                P.status == PaymentStatus.CONFIRMED
            )
        )
        revenue = int(rev_result.scalar() or 0)

        # Активные подписки
        active_sub_result = await session.execute(
            select(func.count(S.id)).filter(S.status == "active")
        )
        active_subs = int(active_sub_result.scalar() or 0)

        # Заявки на рекламу по статусам
        ad_counts = {}
        for st in AdCampaignStatus:
            r = await session.execute(
                select(func.count(A.id)).filter(A.status == st)
            )
            ad_counts[st.value] = int(r.scalar() or 0)

    total_donations = await DonationOrm.get_total()

    return {
        "revenue_kopecks": revenue,
        "active_subscriptions": active_subs,
        "total_donations_kopecks": total_donations,
        "ad_campaigns_by_status": ad_counts,
        "economy_balance": balance_report(),
    }


@router.get("/prices")
async def get_prices(profile: dict = Depends(require_admin_user)):
    """Текущие цены."""
    r = get_redis()
    defaults = {
        "sub_vip": TIER_PRICES_KOPECKS[SubscriptionTier.VIP],
        "sub_premium": TIER_PRICES_KOPECKS[SubscriptionTier.PREMIUM],
        "sub_elite": TIER_PRICES_KOPECKS[SubscriptionTier.ELITE],
        "ad_per_1000": 1000_00,
        "ai_check_enabled": "true",
    }
    result = {}
    for key, redis_key in PRICE_KEYS.items():
        try:
            val = r.get(redis_key)
            result[key] = val if val is not None else defaults[key]
        except Exception:
            result[key] = defaults[key]
    return result


@router.post("/prices")
async def set_prices(body: dict = Body(...), profile: dict = Depends(require_admin_user)):
    """Обновить цены. body: {sub_vip, sub_premium, sub_elite, ad_per_1000, ai_check_enabled}"""
    r = get_redis()
    for key, value in body.items():
        redis_key = PRICE_KEYS.get(key)
        if redis_key and value is not None:
            r.set(redis_key, str(value))
    return {"ok": True}


@router.get("/campaigns")
async def list_campaigns_admin(
    profile: dict = Depends(require_admin_user),
):
    """Список заявок на рекламу (все)."""
    campaigns = await AdCampaignOrm.list_by_status(None)
    return {
        "campaigns": [
            {
                "id": str(c.id),
                "advertiser_id": c.advertiser_id,
                "text": c.text,
                "link": c.link,
                "target_unique_users": c.target_unique_users,
                "price": c.price,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "ai_verdict": c.ai_verdict,
                "admin_comment": c.admin_comment,
                "contact": c.contact,
                "selected_chats": c.selected_chats,
                "actual_reach": c.actual_reach,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            }
            for c in campaigns
        ]
    }


@router.get("/payments")
async def list_payments(
    limit: int = 50, profile: dict = Depends(require_admin_user)
):
    """Последние платежи."""
    from sqlalchemy import select
    from shared.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            select(PaymentOrm).order_by(PaymentOrm.created_at.desc()).limit(limit)
        )
        payments = result.scalars().all()
    return {
        "payments": [
            {
                "order_id": p.order_id,
                "user_id": p.user_id,
                "amount": p.amount,
                "payment_type": p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "fulfilled": p.fulfilled,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ]
    }


@router.get("/admins")
async def list_admins(profile: dict = Depends(require_admin_user)):
    """Список админов (супер-админ: тот, кто в .env)."""
    return {
        "admin_ids": list(_settings.ADMIN_ID_SET),
        "you": profile["id"],
        "is_admin": profile["id"] in _settings.ADMIN_ID_SET,
    }
