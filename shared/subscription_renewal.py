"""Фоновое продление подписок через T-Bank Charge (RebillId)."""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.enums import PaymentStatus, PaymentType, SubscriptionTier
from shared.logger import get_payment_logger
from shared.models.payment import PaymentOrm
from shared.models.subscription import SubscriptionOrm, TIER_PRICES_KOPECKS
from shared.payments import charge_recurring, is_payment_successful

logger = logging.getLogger(__name__)
pay_log = get_payment_logger()


async def process_subscription_renewals() -> dict[str, int]:
    """Продлить все ACTIVE+auto_renew с истёкшим expires_at."""
    stats = {"tried": 0, "ok": 0, "fail": 0, "skipped": 0}
    subs = await SubscriptionOrm.get_active_for_renewal()
    for sub in subs:
        stats["tried"] += 1
        if not sub.recurring_key:
            await SubscriptionOrm.cancel_auto_renew(sub.user_id)
            stats["skipped"] += 1
            pay_log.warning(
                "Renew skip user=%s: no recurring_key, auto_renew off",
                sub.user_id,
            )
            continue
        amount = TIER_PRICES_KOPECKS.get(sub.tier)
        if not amount:
            stats["skipped"] += 1
            continue
        order_id = f"renew_{sub.user_id}_{int(time.time() * 1000)}"
        meta = {"tier": sub.tier.value, "renew": True, "sub_id": sub.id}
        try:
            await PaymentOrm.create(
                order_id, sub.user_id, amount, PaymentType.SUBSCRIPTION, meta
            )
            result = await charge_recurring(
                amount=amount,
                order_id=order_id,
                description=f"Автопродление {sub.tier.value.upper()} (30 дней)",
                rebill_id=str(sub.recurring_key),
                customer_key=str(sub.user_id),
                extra_data={
                    "user_id": str(sub.user_id),
                    "payment_type": "subscription",
                    "renew": "1",
                },
            )
            payment_id = result.get("payment_id")
            status = result.get("status")
            if payment_id:
                try:
                    st = (
                        PaymentStatus.CONFIRMED
                        if is_payment_successful(status)
                        else PaymentStatus.PENDING
                    )
                    # Prefer exact enum if bank status matches
                    try:
                        if status and status in PaymentStatus.__members__:
                            st = PaymentStatus[status]
                    except Exception:
                        pass
                    await PaymentOrm.update_status(order_id, st, payment_id)
                except Exception:
                    pay_log.exception("status update failed order=%s", order_id)

            if result.get("success") and is_payment_successful(status):
                fulfilled_now = await PaymentOrm.mark_fulfilled(order_id)
                if fulfilled_now:
                    await SubscriptionOrm.activate(
                        user_id=sub.user_id,
                        tier=sub.tier,
                        recurring_key=str(sub.recurring_key),
                        auto_renew=True,
                    )
                stats["ok"] += 1
                pay_log.info(
                    "Renew OK user=%s order=%s tier=%s",
                    sub.user_id,
                    order_id,
                    sub.tier.value,
                )
            else:
                stats["fail"] += 1
                pay_log.error(
                    "Renew FAIL user=%s order=%s result=%s",
                    sub.user_id,
                    order_id,
                    {k: result.get(k) for k in ("success", "status", "stage")},
                )
        except Exception:
            stats["fail"] += 1
            pay_log.exception("Renew exception user=%s", sub.user_id)
    return stats
