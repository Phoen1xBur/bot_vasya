"""Роутер платежей Т-Банка.

- POST /api/payments/init — создать платёж (подписка/донат/заказ/реклама)
- POST /api/payments/webhook — приём уведомления от Т-Банка (проверка подписи!)
- GET  /api/payments/status — проверить статус по order_id
"""

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from shared.config import get_settings
from shared.enums import PaymentStatus, PaymentType, SubscriptionTier
from shared.logger import get_payment_logger
from shared.models.donation import DonationOrm
from shared.models.payment import PaymentOrm
from shared.models.subscription import SubscriptionOrm, TIER_PRICES_KOPECKS
from shared.payments import create_payment, get_payment_status, is_payment_successful, verify_webhook_token
from src_fastapi.deps import require_telegram_user

logger = logging.getLogger(__name__)
pay_log = get_payment_logger()
_settings = get_settings()

router = APIRouter(prefix="/api/payments", tags=["Платежи"])


def _make_order_id(prefix: str, user_id: int) -> str:
    return f"{prefix}_{user_id}_{int(time.time() * 1000)}"


@router.post("/init")
async def init_payment(profile: dict = Depends(require_telegram_user), body: dict | None = None):
    """Создание платежа.

    body: {
        payment_type: "subscription" | "donation" | "order" | "ad_campaign",
        amount: int (копейки) — для donation/order/ad_campaign,
        tier: "vip"|"premium"|"elite" — для subscription,
        meta: dict
    }
    """
    body = body or {}
    payment_type = body.get("payment_type", "donation")
    user_id = profile["id"]
    meta: dict = body.get("meta", {})

    if payment_type == "subscription":
        tier_str = body.get("tier", "vip")
        try:
            tier = SubscriptionTier(tier_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный уровень подписки")
        amount = TIER_PRICES_KOPECKS.get(tier)
        if amount is None:
            raise HTTPException(status_code=400, detail="Нельзя купить FREE")
        order_id = _make_order_id("sub", user_id)
        meta = {"tier": tier.value}
        description = f"Подписка {tier.value.upper()} (30 дней)"
        ptype = PaymentType.SUBSCRIPTION
    elif payment_type == "donation":
        amount = int(body.get("amount", 0))
        if amount < 5000:  # мин. 50₽
            raise HTTPException(status_code=400, detail="Минимальная сумма доната — 50₽")
        order_id = _make_order_id("donate", user_id)
        description = "Донат в поддержку проекта Bot Vasya"
        ptype = PaymentType.DONATION
    elif payment_type == "ad_campaign":
        amount = int(body.get("amount", 0))
        campaign_id = body.get("campaign_id")
        order_id = _make_order_id(f"ad_{campaign_id}", user_id)
        description = f"Оплата рекламы (кампания #{campaign_id})"
        meta = {"campaign_id": campaign_id}
        ptype = PaymentType.AD_CAMPAIGN
    else:
        amount = int(body.get("amount", 0))
        order_id = _make_order_id("order", user_id)
        description = body.get("description", "Покупка")
        ptype = PaymentType.ORDER

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    # Сохраняем платёж в БД
    await PaymentOrm.create(order_id, user_id, amount, ptype, meta)

    # Создаём платёж в Т-Банке
    try:
        result = await create_payment(
            amount=amount,
            order_id=order_id,
            description=description,
            extra_data={"user_id": str(user_id), "payment_type": payment_type},
        )
    except Exception as e:
        pay_log.exception("Ошибка создания платежа %s", order_id)
        raise HTTPException(status_code=500, detail=f"Ошибка платёжной системы: {e}")

    if not result.get("payment_url"):
        pay_log.error("Нет payment_url для %s: %s", order_id, result)
        raise HTTPException(status_code=502, detail="Не удалось получить платёжную ссылку")

    # Обновляем payment_id
    if result.get("payment_id"):
        await PaymentOrm.update_status(
            order_id, PaymentStatus.PENDING, result["payment_id"]
        )

    pay_log.info("Платёж создан order=%s user=%s amount=%s", order_id, user_id, amount)
    return {
        "order_id": order_id,
        "payment_url": result["payment_url"],
        "amount": amount,
    }


@router.post("/webhook")
async def payment_webhook(request: Request):
    """Webhook от Т-Банка. Проверка подписи + идемпотентность.

    Т-Банк шлёт POST form-encoded с полями: TerminalKey, OrderId, PaymentId,
    Status, Token, ... Мы проверяем Token и обрабатываем статус.
    """
    try:
        # Т-Банк присылает form-encoded
        form = await request.form()
        payload: dict[str, Any] = {k: str(v) for k, v in form.items()}
    except Exception:
        # Fallback на JSON
        body = await request.body()
        try:
            payload = json.loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Некорректный запрос")

    # 1. Проверка подписи!
    if not verify_webhook_token(payload):
        pay_log.warning("Неверная подпись webhook: %s", payload.get("OrderId"))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверная подпись")

    order_id = payload.get("OrderId", "")
    tb_status = payload.get("Status", "")
    payment_id = payload.get("PaymentId")

    pay_log.info(
        "Webhook: order=%s status=%s payment_id=%s",
        order_id, tb_status, payment_id,
    )

    if not order_id:
        return {"ok": False, "reason": "no order_id"}

    # 2. Идемпотентность — помечаем fulfilled один раз
    payment = await PaymentOrm.get_by_order_id(order_id)
    if payment is None:
        pay_log.warning("Платёж не найден: %s", order_id)
        return {"ok": False, "reason": "payment not found"}

    # Обновляем статус
    try:
        new_status = PaymentStatus(tb_status)
    except ValueError:
        new_status = PaymentStatus.PENDING
    await PaymentOrm.update_status(order_id, new_status, payment_id)

    # 3. Выдача товара — только при успехе и только ОДИН РАЗ
    if is_payment_successful(tb_status):
        fulfilled_now = await PaymentOrm.mark_fulfilled(order_id)
        if not fulfilled_now:
            # Уже было выдано — повторный webhook, игнорируем выдачу
            pay_log.info("Платёж %s уже выдан — пропуск", order_id)
            return {"ok": True, "duplicate": True}

        await _fulfill_payment(payment, payload)
        pay_log.info("Платёж %s выполнен (выдан товар)", order_id)

    return {"ok": True, "status": tb_status}


async def _fulfill_payment(payment: PaymentOrm, payload: dict) -> None:
    """Выдача товара в зависимости от типа платежа."""
    user_id = payment.user_id
    meta = payment.meta or {}
    try:
        if payment.payment_type == PaymentType.SUBSCRIPTION:
            tier_str = meta.get("tier", "vip")
            tier = SubscriptionTier(tier_str)
            recurring = payload.get("RecurringKey") or payload.get("CardId")
            await SubscriptionOrm.activate(
                user_id=user_id,
                tier=tier,
                recurring_key=recurring,
                auto_renew=bool(recurring),
            )
            pay_log.info("Подписка %s активирована для user=%s", tier.value, user_id)

        elif payment.payment_type == PaymentType.DONATION:
            await DonationOrm.create(
                user_id=user_id,
                amount=payment.amount,
                order_id=payment.order_id,
                message=meta.get("message"),
                public=meta.get("public", False),
            )
            pay_log.info("Донат %s копеек от user=%s", payment.amount, user_id)
            # Бонус донатеру: +1000 васякоинов (через бота по событию) —
            # здесь только запись; бот начисляет по уведомлению через шину.

        elif payment.payment_type == PaymentType.AD_CAMPAIGN:
            from shared.enums import AdCampaignStatus
            from shared.models.ad_campaign import AdCampaignOrm

            campaign_id = meta.get("campaign_id")
            if campaign_id:
                await AdCampaignOrm.update(
                    int(campaign_id), status=AdCampaignStatus.PAID
                )
                pay_log.info("Рекламная кампания #%s оплачена", campaign_id)

        elif payment.payment_type == PaymentType.ORDER:
            from shared.models.order import OrderOrm
            o = await OrderOrm.get_by_order_id(payment.order_id)
            if o:
                # fulfilment зависит от продукта
                pay_log.info("Заказ %s (%s) выполнен", payment.order_id, o.product)
    except Exception:
        pay_log.exception("Ошибка выдачи товара order=%s", payment.order_id)


@router.get("/status")
async def check_payment_status_endpoint(order_id: str, profile: dict = Depends(require_telegram_user)):
    """Проверка статуса платежа."""
    payment = await PaymentOrm.get_by_order_id(order_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    if payment.user_id != profile["id"] and profile["id"] not in _settings.ADMIN_ID_SET:
        raise HTTPException(status_code=403, detail="Нет доступа")

    return {
        "order_id": payment.order_id,
        "status": payment.status.value if hasattr(payment.status, "value") else str(payment.status),
        "fulfilled": payment.fulfilled,
        "amount": payment.amount,
        "payment_type": payment.payment_type.value if hasattr(payment.payment_type, "value") else str(payment.payment_type),
    }
