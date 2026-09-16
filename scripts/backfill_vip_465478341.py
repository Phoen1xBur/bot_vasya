"""One-shot: fulfill stuck CONFIRMED subscription for user 465478341."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORDER_ID = "sub_465478341_1789558550174"
USER_ID = 465478341
PAYMENT_ID = "9255165239"


async def main() -> None:
    from shared.enums import PaymentStatus, PaymentType, SubscriptionTier
    from shared.models.payment import PaymentOrm
    from shared.models.subscription import SubscriptionOrm

    payment = await PaymentOrm.get_by_order_id(ORDER_ID)
    if payment is None:
        print(f"payment not found: {ORDER_ID}")
        # still activate VIP if user paid externally
        sub = await SubscriptionOrm.activate(
            user_id=USER_ID,
            tier=SubscriptionTier.VIP,
            recurring_key=None,
            auto_renew=False,
        )
        print(f"activated VIP without payment row: {sub.id} expires={sub.expires_at}")
        return

    print(
        f"found payment id={payment.id} type={payment.payment_type} "
        f"status={payment.status} fulfilled={getattr(payment, 'fulfilled', None)} "
        f"meta={payment.meta}"
    )
    await PaymentOrm.update_status(ORDER_ID, PaymentStatus.CONFIRMED, PAYMENT_ID)

    if payment.payment_type == PaymentType.SUBSCRIPTION:
        tier_str = (payment.meta or {}).get("tier", "vip")
        tier = SubscriptionTier(tier_str)
        sub = await SubscriptionOrm.activate(
            user_id=payment.user_id,
            tier=tier,
            recurring_key=None,
            auto_renew=False,
        )
        print(f"activated {tier.value} for user={payment.user_id} expires={sub.expires_at}")
    else:
        print(f"unexpected payment_type={payment.payment_type}")

    if hasattr(PaymentOrm, "mark_fulfilled"):
        await PaymentOrm.mark_fulfilled(ORDER_ID)
        print("marked fulfilled")
    else:
        print("no mark_fulfilled method — check payment.fulfilled manually")


if __name__ == "__main__":
    asyncio.run(main())
