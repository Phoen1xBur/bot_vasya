"""Роутер рекламы: подача заявок, AI-проверка, админ-управление, таргетинг."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from shared.ad_rules import AD_RULES
from shared.ad_targeting import count_total_unique_users, select_chats_for_target
from shared.ai import ai_check_ad
from shared.config import get_settings
from shared.enums import AdCampaignStatus
from shared.models.ad_campaign import AdCampaignOrm
from src_fastapi.deps import require_admin_user, require_telegram_user

logger = logging.getLogger(__name__)
_settings = get_settings()

router = APIRouter(prefix="/api/ads", tags=["Реклама"])


@router.get("/rules")
async def get_ad_rules():
    """Сводка правил для рекламодателей."""
    return {"rules": AD_RULES, "total_unique_users": await count_total_unique_users()}


@router.post("/campaigns")
async def submit_campaign(
    body: dict = Body(...),
    profile: dict = Depends(require_telegram_user),
):
    """Подача заявки на рекламу рекламодателем.

    body: {text, link, target_unique_users, contact, rules_accepted}
    """
    text = (body.get("text") or "").strip()
    link = (body.get("link") or "").strip()
    target = int(body.get("target_unique_users", 0))
    contact = (body.get("contact") or "").strip()
    rules_accepted = bool(body.get("rules_accepted", False))

    if not text or not link or target <= 0:
        raise HTTPException(status_code=400, detail="Заполните текст, ссылку и целевую аудиторию")
    if not rules_accepted:
        raise HTTPException(status_code=400, detail="Необходимо согласие с правилами")

    # Цена: 1000₽ за 1000 у.п. (по умолчанию, настраивается в админке)
    price_per_1000 = 1000_00  # копеек
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

    # AI-проверка (если включена — по умолчанию включена)
    ai_enabled = True  # можно вынести в настройки админки
    if ai_enabled:
        verdict = await ai_check_ad(text, AD_RULES)
        await AdCampaignOrm.update(
            campaign.id,
            ai_verdict=verdict,
            status=AdCampaignStatus.AI_APPROVED if verdict.get("approved") else AdCampaignStatus.AI_REJECTED,
        )
        campaign = await AdCampaignOrm.get_by_id(campaign.id)

    return {
        "campaign_id": str(campaign.id),
        "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
        "ai_verdict": campaign.ai_verdict,
        "price": campaign.price,
    }


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
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "sent_at": c.sent_at.isoformat() if c.sent_at else None,
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
    """Одобрить заявку. Опционально comment."""
    comment = (body or {}).get("comment", "")
    c = await AdCampaignOrm.update(
        campaign_id,
        status=AdCampaignStatus.APPROVED,
        admin_comment=comment,
    )
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")

    # Подбираем чаты по таргетингу
    result = await select_chats_for_target(c.target_unique_users)
    await AdCampaignOrm.update(
        campaign_id,
        selected_chats=result.selected_chats,
    )
    return {
        "ok": True,
        "campaign_id": str(c.id),
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
    comment = (body or {}).get("comment", "")
    c = await AdCampaignOrm.update(
        campaign_id,
        status=AdCampaignStatus.REJECTED,
        admin_comment=comment,
    )
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return {"ok": True, "campaign_id": str(c.id)}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, profile: dict = Depends(require_telegram_user)):
    """Отчёт рекламодателю по своей кампании."""
    c = await AdCampaignOrm.get_by_id(campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    # рекламодатель видит только свою
    if c.advertiser_id != profile["id"] and profile["id"] not in _settings.ADMIN_ID_SET:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return {
        "id": str(c.id),
        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
        "target_unique_users": c.target_unique_users,
        "actual_reach": c.actual_reach,
        "selected_chats_count": len(c.selected_chats) if c.selected_chats else 0,
        "price": c.price,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
    }
