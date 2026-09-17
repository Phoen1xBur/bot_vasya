"""Роутер админ-панели: статистика, управление, цены.

Доступ: только админы (require_admin_user). Авторизация через initData (HMAC).
"""

import logging
from datetime import datetime
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
)
from shared.redis_client import get_redis
from shared.prices import PRICE_KEYS
from src_fastapi.deps import require_admin_user

logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(prefix="/api/admin", tags=["Админ-панель"])



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
    """Текущие цены (Redis с fallback на дефолты)."""
    from shared.prices import get_admin_prices_snapshot

    return get_admin_prices_snapshot()


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

    from shared.enums import PaymentStatus

    # Скрываем неоплаченные/открытые статусы (NEW/PENDING/AUTHORIZED)
    unpaid = (PaymentStatus.NEW, PaymentStatus.PENDING, PaymentStatus.AUTHORIZED)
    async with async_session_factory() as session:
        result = await session.execute(
            select(PaymentOrm)
            .where(PaymentOrm.status.notin_(unpaid))
            .order_by(PaymentOrm.created_at.desc())
            .limit(limit)
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


@router.get("/subscriptions")
async def list_active_subscriptions(
    limit: int = 200, profile: dict = Depends(require_admin_user)
):
    """Активные платные подписки (VIP/Premium/Elite)."""
    from shared.models.user import UserOrm

    subs = await SubscriptionOrm.list_active(limit=limit)
    out = []
    for s in subs:
        if s.tier == SubscriptionTier.FREE:
            continue
        user = await UserOrm.get_user_by_id(s.user_id)
        payment = await PaymentOrm.get_last_confirmed_subscription(s.user_id)
        out.append(
            {
                "id": s.id,
                "user_id": s.user_id,
                "username": user.username if user else None,
                "first_name": user.first_name if user else None,
                "tier": s.tier.value if hasattr(s.tier, "value") else str(s.tier),
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "auto_renew": bool(s.auto_renew),
                "has_recurring_key": bool(s.recurring_key),
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "payment": (
                    {
                        "order_id": payment.order_id,
                        "payment_id": payment.payment_id,
                        "amount": payment.amount,
                        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
                        "created_at": payment.created_at.isoformat() if payment.created_at else None,
                    }
                    if payment
                    else None
                ),
            }
        )
    return {"subscriptions": out}


@router.post("/subscriptions/{sub_id}/cancel_refund")
async def cancel_and_refund_subscription(
    sub_id: int,
    body: dict = Body(default=None),
    profile: dict = Depends(require_admin_user),
):
    """Отменить подписку + автопродление и вернуть деньги по последнему платежу (идемпотентно)."""
    from shared.enums import PaymentStatus as PS
    from shared.payments import refund_payment
    from shared.logger import get_payment_logger

    pay_log = get_payment_logger()
    body = body or {}
    confirm = bool(body.get("confirm"))
    if not confirm:
        raise HTTPException(status_code=400, detail="Требуется confirm=true")

    from shared.database import async_session_factory
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(SubscriptionOrm).filter(SubscriptionOrm.id == sub_id))
        sub = result.scalars().first()
    if sub is None:
        raise HTTPException(status_code=404, detail="Подписка не найдена")

    # Идемпотентность: уже отменена
    already_cancelled = (
        (sub.status.value if hasattr(sub.status, "value") else str(sub.status)) == "cancelled"
    )

    payment = await PaymentOrm.get_last_confirmed_subscription(sub.user_id)
    refund_result = None
    refund_skipped = None

    if payment is None:
        refund_skipped = "no_confirmed_payment"
    elif not payment.payment_id:
        refund_skipped = "no_payment_id"
    elif (payment.status.value if hasattr(payment.status, "value") else str(payment.status)) == "REFUNDED":
        refund_skipped = "already_refunded"
    else:
        try:
            refund_result = await refund_payment(payment.payment_id, payment.amount)
            if refund_result.get("success"):
                await PaymentOrm.update_status(payment.order_id, PS.REFUNDED, payment.payment_id)
            else:
                pay_log.warning(
                    "Admin refund failed sub=%s payment_id=%s raw=%s",
                    sub_id,
                    payment.payment_id,
                    refund_result.get("raw"),
                )
        except Exception as e:
            pay_log.exception("Admin refund error sub=%s", sub_id)
            raise HTTPException(status_code=502, detail=f"Ошибка возврата Т-Банк: {e}")

    if not already_cancelled:
        sub = await SubscriptionOrm.force_cancel(sub_id)
    else:
        # всё равно сбросим auto_renew/recurring
        sub = await SubscriptionOrm.force_cancel(sub_id)

    logger.info(
        "Admin %s cancel_refund sub=%s user=%s refund_skipped=%s refund_ok=%s",
        profile["id"],
        sub_id,
        sub.user_id if sub else None,
        refund_skipped,
        (refund_result or {}).get("success"),
    )

    return {
        "ok": True,
        "subscription_id": sub_id,
        "status": sub.status.value if sub and hasattr(sub.status, "value") else "cancelled",
        "auto_renew": False,
        "refund": refund_result,
        "refund_skipped": refund_skipped,
        "payment_order_id": payment.order_id if payment else None,
        "idempotent": already_cancelled and refund_skipped in ("already_refunded", "no_confirmed_payment", "no_payment_id"),
    }


async def _resolve_target_user(body: dict) -> tuple[int, str | None]:
    """Resolve telegram user by user_id or username. Returns (user_id, username)."""
    from shared.models.user import UserOrm

    raw_id = body.get("user_id") or body.get("telegram_id")
    username = body.get("username")
    if isinstance(username, str):
        username = username.strip().lstrip("@") or None

    if raw_id is not None and str(raw_id).strip() != "":
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="user_id должен быть числом")
        if user_id <= 0:
            raise HTTPException(status_code=400, detail="user_id должен быть положительным")
        user = await UserOrm.get_user_by_id(user_id)
        return user_id, (user.username if user else username)

    if username:
        user = await UserOrm.get_by_username(username)
        if user is None:
            raise HTTPException(
                status_code=404,
                detail=f"Пользователь @{username} не найден в БД бота",
            )
        return int(user.user_id), user.username

    raise HTTPException(status_code=400, detail="Укажите user_id или username")


@router.post("/grant/subscription")
async def grant_subscription(
    body: dict = Body(...), profile: dict = Depends(require_admin_user)
):
    """Выдать VIP/Premium/Elite до даты expires_at (ISO) или на days дней."""
    from datetime import timedelta

    from shared.enums import SubscriptionTier
    from shared.models.subscription import SubscriptionOrm

    user_id, username = await _resolve_target_user(body)
    tier_raw = str(body.get("tier") or "").strip().lower()
    tier_map = {
        "vip": SubscriptionTier.VIP,
        "premium": SubscriptionTier.PREMIUM,
        "elite": SubscriptionTier.ELITE,
    }
    if tier_raw not in tier_map:
        raise HTTPException(status_code=400, detail="tier: vip | premium | elite")
    tier = tier_map[tier_raw]

    expires_raw = body.get("expires_at") or body.get("end_date")
    days = body.get("days")
    if expires_raw:
        try:
            expires_at = datetime.fromisoformat(
                str(expires_raw).replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            raise HTTPException(status_code=400, detail="expires_at: ожидается ISO-дата")
    elif days is not None:
        try:
            days_i = int(days)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="days должен быть числом")
        if days_i < 1 or days_i > 3650:
            raise HTTPException(status_code=400, detail="days: 1..3650")
        expires_at = datetime.now().replace(microsecond=0) + timedelta(days=days_i)
    else:
        raise HTTPException(status_code=400, detail="Укажите expires_at или days")

    try:
        sub = await SubscriptionOrm.admin_grant(
            user_id=user_id,
            tier=tier,
            expires_at=expires_at,
            auto_renew=bool(body.get("auto_renew", False)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        "ADMIN_AUDIT grant_subscription admin=%s target=%s(@%s) tier=%s expires=%s",
        profile["id"],
        user_id,
        username,
        tier.value,
        expires_at.isoformat(),
    )
    return {
        "ok": True,
        "user_id": user_id,
        "username": username,
        "tier": tier.value,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "subscription_id": sub.id,
    }


@router.post("/grant/coins")
async def grant_coins(body: dict = Body(...), profile: dict = Depends(require_admin_user)):
    """Начислить (или списать) васякоины пользователю в указанном чате."""
    from shared.models.chat import TelegramChatOrm
    from shared.models.group_user import GroupUserOrm
    from shared.models.user import UserOrm

    user_id, username = await _resolve_target_user(body)
    try:
        chat_id = int(body.get("chat_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Укажите chat_id (Telegram chat id)")
    try:
        amount = int(body.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount должен быть целым числом")
    if amount == 0:
        raise HTTPException(status_code=400, detail="amount не должен быть 0")
    if abs(amount) > 10_000_000:
        raise HTTPException(status_code=400, detail="amount слишком большой")

    await UserOrm.insert_or_update_user(user_id)
    try:
        await TelegramChatOrm.insert_or_update_telegram_chat(chat_id)
    except Exception:
        logger.exception("grant_coins: chat upsert failed chat_id=%s", chat_id)

    gu = await GroupUserOrm.get_group_user(user_id, chat_id)
    if gu is None:
        gu = await GroupUserOrm.insert_or_update_group_user(user_id, chat_id, money=0)

    if amount > 0:
        await gu.money_plus(amount)
    else:
        gu = await GroupUserOrm.get_group_user(user_id, chat_id)
        if gu is None or gu.money < abs(amount):
            raise HTTPException(status_code=400, detail="Недостаточно васякоинов для списания")
        await gu.money_minus(abs(amount))

    gu2 = await GroupUserOrm.get_group_user(user_id, chat_id)
    balance = int(gu2.money) if gu2 else None
    logger.info(
        "ADMIN_AUDIT grant_coins admin=%s target=%s(@%s) chat=%s amount=%s balance=%s",
        profile["id"],
        user_id,
        username,
        chat_id,
        amount,
        balance,
    )
    return {
        "ok": True,
        "user_id": user_id,
        "username": username,
        "chat_id": chat_id,
        "amount": amount,
        "balance": balance,
    }
