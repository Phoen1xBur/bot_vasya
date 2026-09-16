"""Callback'и подписок и донатов: создание платежа → кнопка с платёжной ссылкой."""
import logging
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shared.ai import ai_thank_donor
from shared.config import get_settings
from shared.enums import PaymentStatus, PaymentType, SubscriptionTier
from shared.logger import get_payment_logger
from shared.models.donation import DonationOrm
from shared.models.payment import PaymentOrm
from shared.models.subscription import SubscriptionOrm, TIER_PRICES_KOPECKS
from shared.payments import create_payment

router = Router(name=__name__)
logger = logging.getLogger(__name__)
pay_log = get_payment_logger()
_settings = get_settings()


def _make_order_id(prefix: str, user_id: int) -> str:
    return f"{prefix}_{user_id}_{int(time.time() * 1000)}"


async def _start_payment(callback: CallbackQuery, amount: int, order_id: str, description: str, payment_type: PaymentType, meta: dict):
    """Создаёт платёж в БД и Т-Банке, отправляет кнопку со ссылкой."""
    user_id = callback.from_user.id
    await PaymentOrm.create(order_id, user_id, amount, payment_type, meta)
    try:
        result = await create_payment(
            amount=amount,
            order_id=order_id,
            description=description,
            extra_data={"user_id": str(user_id)},
        )
    except Exception as e:
        pay_log.exception("Ошибка создания платежа %s", order_id)
        await callback.answer(f"Ошибка платёжной системы: {e}", show_alert=True)
        return

    if not result.get("payment_url"):
        await callback.answer("Не удалось получить платёжную ссылку", show_alert=True)
        return

    if result.get("payment_id"):
        await PaymentOrm.update_status(order_id, PaymentStatus.PENDING, result["payment_id"])

    pay_log.info("Платёж создан order=%s user=%s amount=%s", order_id, user_id, amount)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=result["payment_url"])]]
    )
    rubles = amount / 100
    await callback.message.edit_text(
        f"💳 К оплате: {rubles:.0f}₽\nПосле оплаты функция активируется автоматически.",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:buy:"))
async def on_buy_subscription(callback: CallbackQuery):
    tier_str = callback.data.split(":")[-1]
    try:
        tier = SubscriptionTier(tier_str)
    except ValueError:
        await callback.answer("Неверный уровень", show_alert=True)
        return
    amount = TIER_PRICES_KOPECKS.get(tier)
    if amount is None:
        await callback.answer("Этот уровень нельзя купить", show_alert=True)
        return
    order_id = _make_order_id("sub", callback.from_user.id)
    description = f"Подписка {tier.value.upper()} (30 дней)"
    await _start_payment(
        callback, amount, order_id, description, PaymentType.SUBSCRIPTION, {"tier": tier.value}
    )


@router.callback_query(F.data == "sub:cancel")
async def on_cancel_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    cancelled = await SubscriptionOrm.cancel_auto_renew(user_id)
    if not cancelled:
        await callback.answer("Нечего отменять: активной подписки нет. Выберите тариф выше.", show_alert=True)
        return
    sub = await SubscriptionOrm.get_by_user(user_id)
    expires = sub.expires_at.strftime("%d.%m.%Y") if sub and sub.expires_at else "—"
    await callback.message.edit_text(
        f"Автопродление отключено.\nПодписка действует до {expires}."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("donate:"))
async def on_donate(callback: CallbackQuery):
    amount_str = callback.data.split(":")[-1]
    if amount_str == "custom":
        await callback.answer("Введите сумму командой: /donate_amount <сумма>", show_alert=True)
        return
    try:
        rubles = int(amount_str)
    except ValueError:
        await callback.answer("Неверная сумма", show_alert=True)
        return
    amount = rubles * 100  # в копейки
    order_id = _make_order_id("donate", callback.from_user.id)
    description = "Донат в поддержку проекта Bot Vasya"
    await _start_payment(
        callback, amount, order_id, description, PaymentType.DONATION, {"public": False}
    )
