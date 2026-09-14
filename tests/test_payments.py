"""Тесты платежей Т-Банка: ORM, идемпотентность выдачи, верификация webhook.

Сценарии (из ТЗ): создание платежа, webhook (проверка подписи + идемпотентность),
выдача подписки только один раз.
"""
import pytest

import shared.payments as pay_mod
from shared.enums import PaymentStatus, PaymentType
from shared.models.payment import PaymentOrm
from shared.payments import is_payment_successful


# ----------------- ORM платежей -----------------


async def test_create_and_get_payment(db):
    p = await PaymentOrm.create("order_1", 42, 5000, PaymentType.DONATION, {"note": "x"})
    assert p.order_id == "order_1"
    assert p.amount == 5000
    assert p.payment_type == PaymentType.DONATION
    assert p.fulfilled is False

    fetched = await PaymentOrm.get_by_order_id("order_1")
    assert fetched is not None
    assert fetched.user_id == 42


async def test_update_payment_status(db):
    await PaymentOrm.create("order_2", 1, 100, PaymentType.ORDER)
    await PaymentOrm.update_status("order_2", PaymentStatus.CONFIRMED, "pid_99")
    p = await PaymentOrm.get_by_order_id("order_2")
    assert p.status == PaymentStatus.CONFIRMED
    assert p.payment_id == "pid_99"


async def test_mark_fulfilled_idempotent(db):
    """Повторные webhook не выдают товар дважды."""
    await PaymentOrm.create("order_3", 1, 100, PaymentType.DONATION)
    # Первая пометка — True (только что выдан)
    assert await PaymentOrm.mark_fulfilled("order_3") is True
    # Повторная — False (уже выдан, пропуск)
    assert await PaymentOrm.mark_fulfilled("order_3") is False
    p = await PaymentOrm.get_by_order_id("order_3")
    assert p.fulfilled is True


async def test_mark_fulfilled_missing_payment(db):
    assert await PaymentOrm.mark_fulfilled("does_not_exist") is False


# ----------------- Статусы -----------------


def test_is_payment_successful():
    assert is_payment_successful("CONFIRMED") is True
    assert is_payment_successful("NEW") is False
    assert is_payment_successful("PENDING") is False
    assert is_payment_successful(None) is False


# ----------------- Верификация webhook -----------------


def _patch_tbank(monkeypatch, signature: str = "valid_sig"):
    """Подменяет tbank-securepay фейком: append_token всегда ставит Token=signature."""
    def fake_append_token(data, password):
        d = dict(data)
        d["Token"] = signature
        return d

    monkeypatch.setattr(pay_mod, "_import_tbank", lambda: (None, fake_append_token))
    monkeypatch.setattr(pay_mod._settings, "TBANK_TERMINAL_PASSWORD", "pass")


def test_verify_webhook_valid(monkeypatch, db):
    _patch_tbank(monkeypatch, "valid_sig")
    payload = {"OrderId": "o1", "Status": "CONFIRMED", "Token": "valid_sig"}
    assert pay_mod.verify_webhook_token(payload) is True


def test_verify_webhook_bad_signature(monkeypatch, db):
    _patch_tbank(monkeypatch, "valid_sig")
    payload = {"OrderId": "o1", "Status": "CONFIRMED", "Token": "hacked"}
    assert pay_mod.verify_webhook_token(payload) is False


def test_verify_webhook_no_token(monkeypatch, db):
    _patch_tbank(monkeypatch, "valid_sig")
    assert pay_mod.verify_webhook_token({"OrderId": "o1", "Status": "CONFIRMED"}) is False
