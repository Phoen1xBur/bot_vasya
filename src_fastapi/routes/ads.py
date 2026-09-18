"""Роутер рекламы: подача заявок, AI-проверка, админ-управление, таргетинг.

Поток (2026-09-18):
  submit (ориентировочная цена) → admin_pending
  → admin (edit text + final price) → admin_approved_awaiting_client
  → client confirm + pay (final price) → paid → broadcast
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from shared.ad_rules import AD_RULES
from shared.ad_targeting import count_total_unique_users, select_chats_for_target
from shared.ai import ai_check_ad
from shared.prices import get_ad_price_per_1000_kopecks, is_ad_ai_check_enabled
from shared.config import get_settings
from shared.enums import AdCampaignStatus
from shared.models.ad_campaign import AdCampaignOrm
from src_fastapi.deps import require_admin_user, require_telegram_user

logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(prefix="/api/ads", tags=["Реклама"])

# Statuses where client may pay (admin already set final price)
PAYABLE_STATUSES = {
    AdCampaignStatus.ADMIN_APPROVED_AWAITING_CLIENT.value,
    AdCampaignStatus.AWAITING_PAYMENT.value,
    AdCampaignStatus.APPROVED.value,  # legacy
}

# Statuses admin can approve/reject from
ADMIN_REVIEWABLE = {
    AdCampaignStatus.ADMIN_PENDING.value,
    AdCampaignStatus.AI_PENDING.value,
    AdCampaignStatus.AI_APPROVED.value,  # legacy backlog
}


def _status_val(c) -> str:
    return c.status.value if hasattr(c.status, "value") else str(c.status)


def _campaign_public(c: AdCampaignOrm) -> dict:
    return {
        "id": str(c.id),
        "campaign_id": str(c.id),
        "advertiser_id": c.advertiser_id,
        "text": c.text,
        "link": c.link,
        "target_unique_users": c.target_unique_users,
        "price": c.price,
        "status": _status_val(c),
        "ai_verdict": c.ai_verdict,
        "admin_comment": c.admin_comment,
        "contact": c.contact,
        "selected_chats_count": len(c.selected_chats) if c.selected_chats else 0,
        "actual_reach": c.actual_reach,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        "price_is_estimate": _status_val(c) in {
            AdCampaignStatus.DRAFT.value,
            AdCampaignStatus.AI_PENDING.value,
            AdCampaignStatus.AI_APPROVED.value,
            AdCampaignStatus.ADMIN_PENDING.value,
            AdCampaignStatus.AI_REJECTED.value,
        },
        "can_pay": _status_val(c) in PAYABLE_STATUSES and int(c.price or 0) > 0,
    }


async def _notify_admins_new_campaign(campaign: AdCampaignOrm) -> None:
    try:
        from shared.messaging import get_bus

        bus = get_bus()
        price_rub = (campaign.price or 0) / 100.0
        text = (
            f"📢 Новая заявка на рекламу #{campaign.id}\n"
            f"От: {campaign.advertiser_id}\n"
            f"Охват: {campaign.target_unique_users}\n"
            f"Ориентировочная цена: {price_rub:.0f} ₽\n"
            f"Статус: {_status_val(campaign)}\n\n"
            f"{(campaign.text or '')[:400]}"
        )
        await bus.publish(
            "api.ad.submitted",
            {
                "admin_ids": list(_settings.ADMIN_ID_SET),
                "text": text,
                "campaign_id": campaign.id,
                "advertiser_id": campaign.advertiser_id,
            },
        )
    except Exception:
        logger.exception("notify admins new campaign failed id=%s", campaign.id)


async def _notify_client_approved(campaign: AdCampaignOrm) -> None:
    try:
        from shared.messaging import get_bus

        bus = get_bus()
        base = (_settings.WEBAPP_BASE_URL or "").rstrip("/")
        url = f"{base}/webapp/?page=advertise&campaign_id={campaign.id}"
        price_rub = (campaign.price or 0) / 100.0
        text = (
            f"✅ Реклама #{campaign.id} одобрена админом.\n"
            f"Итоговая цена: {price_rub:.0f} ₽\n"
            f"Проверьте текст и подтвердите оплату:\n{url}"
        )
        await bus.publish(
            "api.ad.approved",
            {
                "user_id": campaign.advertiser_id,
                "text": text,
                "campaign_id": campaign.id,
                "webapp_url": url,
            },
        )
    except Exception:
        logger.exception("notify client approved failed id=%s", campaign.id)


@router.get("/rules")
async def get_ad_rules():
    """Сводка правил для рекламодателей."""
    return {
        "rules": AD_RULES,
        "total_unique_users": await count_total_unique_users(),
        "price_per_1000": get_ad_price_per_1000_kopecks(),
    }


@router.post("/campaigns")
async def submit_campaign(
    body: dict = Body(...),
    profile: dict = Depends(require_telegram_user),
):
    """Подача заявки: ориентировочная цена из Redis-тарифа, затем модерация админом."""
    text = (body.get("text") or "").strip()
    link = (body.get("link") or "").strip()
    target = int(body.get("target_unique_users", 0))
    contact = (body.get("contact") or "").strip()
    rules_accepted = bool(body.get("rules_accepted", False))

    if not text or not link or target <= 0:
        raise HTTPException(status_code=400, detail="Заполните текст, ссылку и целевую аудиторию")
    if not rules_accepted:
        raise HTTPException(status_code=400, detail="Необходимо согласие с правилами")

    # Ориентировочная цена (не финальная) — админ задаст итоговую при одобрении
    price_per_1000 = get_ad_price_per_1000_kopecks()
    price = (target // 1000) * price_per_1000
    if target % 1000:
        price += price_per_1000

    campaign = await AdCampaignOrm.create(
        advertiser_id=profile["id"],
        text=text,
        link=link,
        target_unique_users=target,
        price=price,
        contact=contact,
        status=AdCampaignStatus.AI_PENDING,
    )

    # AI — подсказка модератору. Платить нельзя до админ-одобрения с финальной ценой.
    if is_ad_ai_check_enabled():
        verdict = await ai_check_ad(text, AD_RULES)
        if verdict.get("error") or verdict.get("reason") == "Ошибка AI-проверки":
            status = AdCampaignStatus.ADMIN_PENDING
            base = verdict if isinstance(verdict, dict) else {}
            verdict = {
                **base,
                "approved": None,
                "error": True,
                "reason": "Ошибка AI-проверки — заявка ушла на ручную модерацию",
            }
        elif verdict.get("approved"):
            # AI ок → всё равно ждём админа (финальная цена + правка текста)
            status = AdCampaignStatus.ADMIN_PENDING
        else:
            status = AdCampaignStatus.AI_REJECTED
        await AdCampaignOrm.update(campaign.id, ai_verdict=verdict, status=status)
        campaign = await AdCampaignOrm.get_by_id(campaign.id)
    else:
        verdict = {"ok": True, "skipped": True, "approved": True}
        await AdCampaignOrm.update(
            campaign.id,
            ai_verdict=verdict,
            status=AdCampaignStatus.ADMIN_PENDING,
        )
        campaign = await AdCampaignOrm.get_by_id(campaign.id)

    if campaign and _status_val(campaign) == AdCampaignStatus.ADMIN_PENDING.value:
        await _notify_admins_new_campaign(campaign)

    return {
        "campaign_id": str(campaign.id),
        "status": _status_val(campaign),
        "ai_verdict": campaign.ai_verdict,
        "price": campaign.price,
        "price_is_estimate": True,
        "text": campaign.text,
        "can_pay": False,
    }


@router.get("/my-campaigns")
async def my_campaigns(profile: dict = Depends(require_telegram_user)):
    """Список кампаний текущего рекламодателя."""
    rows = await AdCampaignOrm.list_by_advertiser(profile["id"])
    return {"campaigns": [_campaign_public(c) for c in rows]}


@router.get("/campaigns")
async def list_campaigns(
    status: str | None = Query(default=None),
    profile: dict = Depends(require_admin_user),
):
    """Список заявок (только админ). Фильтр по статусу."""
    status_enum = None
    if status:
        try:
            status_enum = AdCampaignStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный статус")
    campaigns = await AdCampaignOrm.list_by_status(status_enum)
    return {
        "campaigns": [
            {
                **_campaign_public(c),
                "selected_chats": c.selected_chats,
            }
            for c in campaigns
        ]
    }


@router.post("/campaigns/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: str,
    body: dict = Body(default=None),
    profile: dict = Depends(require_admin_user),
):
    """Одобрить заявку: обязательна финальная цена; опционально правка текста."""
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Неверный id кампании")

    body = body or {}
    comment = (body.get("comment") or "").strip()
    new_text = body.get("text")
    if isinstance(new_text, str):
        new_text = new_text.strip()
    else:
        new_text = None

    existing = await AdCampaignOrm.get_by_id(cid)
    if existing is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")

    st = _status_val(existing)
    if st in (
        AdCampaignStatus.REJECTED.value,
        AdCampaignStatus.PAID.value,
        AdCampaignStatus.SENDING.value,
        AdCampaignStatus.SENT.value,
        AdCampaignStatus.CANCELLED.value,
        AdCampaignStatus.ADMIN_APPROVED_AWAITING_CLIENT.value,
        AdCampaignStatus.AWAITING_PAYMENT.value,
    ):
        raise HTTPException(status_code=400, detail=f"Нельзя одобрить кампанию со статусом {st}")

    # Final price: kopecks via `price`, or rubles via `price_rub` / `final_price_rub`
    final_price = None
    if body.get("price") is not None and str(body.get("price")).strip() != "":
        try:
            final_price = int(body.get("price"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Неверная цена (price, копейки)")
    elif body.get("price_rub") is not None and str(body.get("price_rub")).strip() != "":
        try:
            final_price = int(round(float(body.get("price_rub")) * 100))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Неверная цена (price_rub)")
    elif body.get("final_price_rub") is not None and str(body.get("final_price_rub")).strip() != "":
        try:
            final_price = int(round(float(body.get("final_price_rub")) * 100))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Неверная цена (final_price_rub)")

    if final_price is None:
        # Keep existing only if admin explicitly confirms reuse; otherwise require set
        if int(existing.price or 0) <= 0:
            raise HTTPException(
                status_code=400,
                detail="Укажите итоговую цену (price в копейках или price_rub)",
            )
        final_price = int(existing.price)
    if final_price <= 0:
        raise HTTPException(status_code=400, detail="Итоговая цена должна быть > 0")

    updates: dict = {
        "status": AdCampaignStatus.ADMIN_APPROVED_AWAITING_CLIENT,
        "admin_comment": comment or existing.admin_comment,
        "price": final_price,
    }
    if new_text:
        updates["text"] = new_text

    c = await AdCampaignOrm.update(cid, **updates)
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")

    # Подбираем чаты по таргетингу заранее (до оплаты)
    result = await select_chats_for_target(c.target_unique_users)
    c = await AdCampaignOrm.update(
        cid,
        selected_chats=result.selected_chats,
        actual_reach=result.total_unique_users,
    )
    await _notify_client_approved(c)

    return {
        "ok": True,
        "campaign_id": str(c.id),
        "status": _status_val(c),
        "price": c.price,
        "text": c.text,
        "selected_chats": result.selected_chats,
        "actual_unique_users": result.total_unique_users,
        "within_tolerance": result.within_tolerance,
    }


@router.post("/campaigns/{campaign_id}/reject")
async def reject_campaign(
    campaign_id: str,
    body: dict = Body(default=None),
    profile: dict = Depends(require_admin_user),
):
    """Отклонить заявку."""
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Неверный id кампании")
    comment = (body or {}).get("comment", "")
    c = await AdCampaignOrm.update(
        cid,
        status=AdCampaignStatus.REJECTED,
        admin_comment=comment,
    )
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return {"ok": True, "campaign_id": str(c.id), "status": _status_val(c)}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, profile: dict = Depends(require_telegram_user)):
    """Отчёт / подтверждение рекламодателю по своей кампании."""
    try:
        cid = int(campaign_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Неверный id кампании")
    c = await AdCampaignOrm.get_by_id(cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    if c.advertiser_id != profile["id"] and profile["id"] not in _settings.ADMIN_ID_SET:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return _campaign_public(c)
