"""Тесты подписок: активация, продление, отмена автопродления, истечение."""
from datetime import datetime, timedelta

from shared.database import async_session_factory
from shared.enums import SubscriptionStatus, SubscriptionTier
from shared.models.subscription import SubscriptionOrm


async def test_activate_new_subscription(db):
    sub = await SubscriptionOrm.activate(1001, SubscriptionTier.VIP)
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.tier == SubscriptionTier.VIP
    assert sub.expires_at is not None
    assert sub.auto_renew is True

    active = await SubscriptionOrm.get_active(1001)
    assert active is not None
    assert active.tier == SubscriptionTier.VIP


async def test_activate_extends_existing(db):
    """Активация повторно продлевает expires_at на 30 дней."""
    await SubscriptionOrm.activate(1002, SubscriptionTier.VIP)
    first = await SubscriptionOrm.get_active(1002)
    first_expires = first.expires_at

    await SubscriptionOrm.activate(1002, SubscriptionTier.PREMIUM)
    second = await SubscriptionOrm.get_active(1002)
    assert second.tier == SubscriptionTier.PREMIUM
    assert second.expires_at > first_expires
    # продление примерно на 30 дней
    delta = second.expires_at - first_expires
    assert timedelta(days=29) <= delta <= timedelta(days=31)


async def test_cancel_auto_renew(db):
    """Отмена выключает автопродление, но период доигрывается до конца."""
    await SubscriptionOrm.activate(1003, SubscriptionTier.ELITE, auto_renew=True)
    assert await SubscriptionOrm.cancel_auto_renew(1003) is True

    sub = await SubscriptionOrm.get_active(1003)
    assert sub is not None
    assert sub.auto_renew is False
    # подписка остаётся активной до конца оплаченного периода
    assert sub.status == SubscriptionStatus.ACTIVE


async def test_cancel_no_active_subscription(db):
    assert await SubscriptionOrm.cancel_auto_renew(999999) is False


async def test_expire_overdue_marks_expired(db):
    await SubscriptionOrm.activate(1004, SubscriptionTier.VIP)
    active = await SubscriptionOrm.get_active(1004)
    # Искусственно сдвигаем срок в прошлое
    async with async_session_factory() as session:
        s = await session.get(SubscriptionOrm, active.id)
        s.expires_at = datetime.now() - timedelta(days=1)
        await session.commit()

    n = await SubscriptionOrm.expire_overdue()
    assert n >= 1
    assert await SubscriptionOrm.get_active(1004) is None
