"""Интеграция с Т-Банком (Т-Касса) через tbank-securepay.

- Создание платежа (Init), в т.ч. родительский рекуррентный
- Charge по RebillId
- Верификация webhook (Token)
- Проверка статуса / отмена / refund
"""

from __future__ import annotations

import logging
from typing import Any

from shared.config import get_settings
from shared.logger import get_payment_logger

logger = logging.getLogger(__name__)
pay_log = get_payment_logger()

_settings = get_settings()

_AsyncTKassaClient = None
_append_token = None


def _import_tbank():
    global _AsyncTKassaClient, _append_token
    if _AsyncTKassaClient is None:
        from tbank_securepay import AsyncTKassaClient  # type: ignore
        from tbank_securepay.signing import append_token  # type: ignore

        _AsyncTKassaClient = AsyncTKassaClient
        _append_token = append_token
    return _AsyncTKassaClient, _append_token


def _make_client(AsyncTKassaClient):
    """Собрать AsyncTKassaClient; при TBANK_SSL_VERIFY=false — свой httpx без verify.

    Библиотека не принимает verify= в конструкторе (только client=), поэтому
    старый kwargs["verify"]=False молча отбрасывался и SSL снова падал.
    """
    import httpx

    kwargs: dict = {
        "terminal_key": _settings.TBANK_TERMINAL_ID,
        "password": _settings.TBANK_TERMINAL_PASSWORD,
    }
    if not _settings.TBANK_SSL_VERIFY:
        logger.warning(
            "TBANK_SSL_VERIFY=false — TLS verification DISABLED for T-Bank HTTP client"
        )
        kwargs["client"] = httpx.AsyncClient(timeout=60.0, verify=False)
        client = AsyncTKassaClient(**kwargs)
        # library sets _own_client=False for injected clients; force close on aexit
        client._own_client = True
        return client
    return AsyncTKassaClient(**kwargs)


def verify_webhook_token(payload: dict[str, Any]) -> bool:
    """Проверка подписи webhook от Т-Банка."""
    try:
        _, append_token = _import_tbank()
        if not _settings.TBANK_TERMINAL_PASSWORD:
            logger.error("TBANK_TERMINAL_PASSWORD не задан — webhook не проверяется")
            return False
        received_token = payload.get("Token", "")
        if not received_token:
            return False
        data = {k: v for k, v in payload.items() if k != "Token"}
        signed = append_token(data, _settings.TBANK_TERMINAL_PASSWORD)
        import hmac

        return hmac.compare_digest(signed.get("Token", ""), received_token)
    except Exception:
        logger.exception("Ошибка верификации webhook Т-Банка")
        return False


def _init_body(
    *,
    amount: int,
    order_id: str,
    description: str,
    extra_data: dict[str, str] | None = None,
    customer_key: str | None = None,
    recurrent: bool = False,
    operation_initiator_type: str | None = None,
) -> dict[str, Any]:
    """PascalCase body for /v2/Init."""
    body: dict[str, Any] = {
        "Amount": int(amount),
        "OrderId": order_id,
        "Description": description[:140],
    }
    if _settings.tbank_success_url:
        body["SuccessURL"] = _settings.tbank_success_url
    if _settings.tbank_fail_url:
        body["FailURL"] = _settings.tbank_fail_url
    if _settings.tbank_notification_url:
        body["NotificationURL"] = _settings.tbank_notification_url
    if extra_data:
        body["DATA"] = extra_data
    if customer_key:
        body["CustomerKey"] = str(customer_key)
    if recurrent:
        body["Recurrent"] = "Y"
        # Parent CIT card-on-file; required when Recurrent=Y for card
        body["OperationInitiatorType"] = operation_initiator_type or "1"
    elif operation_initiator_type:
        body["OperationInitiatorType"] = operation_initiator_type
    return body


async def create_payment(
    amount: int,
    order_id: str,
    description: str,
    extra_data: dict[str, str] | None = None,
    *,
    customer_key: str | None = None,
    recurrent: bool = False,
    operation_initiator_type: str | None = None,
) -> dict[str, Any]:
    """Создать платёж через Init (PascalCase).

    Для подписки (родительский): recurrent=True, customer_key=user_id,
    OperationInitiatorType=1 → в webhook придёт RebillId.
    """
    AsyncTKassaClient, _ = _import_tbank()
    pay_log.info(
        "Создание платежа order=%s amount=%s recurrent=%s customer=%s",
        order_id,
        amount,
        recurrent,
        customer_key,
    )

    body = _init_body(
        amount=amount,
        order_id=order_id,
        description=description,
        extra_data=extra_data,
        customer_key=customer_key,
        recurrent=recurrent,
        operation_initiator_type=operation_initiator_type,
    )

    async with _make_client(AsyncTKassaClient) as client:
        try:
            raw = await client.post("Init", body)
            return {
                "success": bool(raw.get("Success", False)),
                "payment_url": raw.get("PaymentURL"),
                "payment_id": str(raw.get("PaymentId")) if raw.get("PaymentId") else None,
                "order_id": raw.get("OrderId"),
                "status": raw.get("Status"),
                "raw": raw,
            }
        except Exception:
            pay_log.exception("Ошибка создания платежа order=%s", order_id)
            raise


async def charge_recurring(
    *,
    amount: int,
    order_id: str,
    description: str,
    rebill_id: str,
    customer_key: str | None = None,
    extra_data: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Init + Charge по сохранённому RebillId (MIT recurring)."""
    AsyncTKassaClient, _ = _import_tbank()
    pay_log.info(
        "Рекуррентный Charge order=%s amount=%s rebill=%s",
        order_id,
        amount,
        rebill_id,
    )

    init_body = _init_body(
        amount=amount,
        order_id=order_id,
        description=description,
        extra_data=extra_data,
        customer_key=customer_key,
        recurrent=False,
        operation_initiator_type="R",
    )

    async with _make_client(AsyncTKassaClient) as client:
        try:
            init_raw = await client.post("Init", init_body)
            if not init_raw.get("Success") or not init_raw.get("PaymentId"):
                pay_log.error("Init for Charge failed order=%s raw=%s", order_id, init_raw)
                return {
                    "success": False,
                    "payment_id": None,
                    "status": init_raw.get("Status"),
                    "raw": init_raw,
                    "stage": "init",
                }
            payment_id = str(init_raw["PaymentId"])
            charge_raw = await client.post(
                "Charge",
                {"PaymentId": payment_id, "RebillId": str(rebill_id)},
            )
            success = bool(charge_raw.get("Success", False))
            status = charge_raw.get("Status")
            pay_log.info(
                "Charge result order=%s payment_id=%s success=%s status=%s",
                order_id,
                payment_id,
                success,
                status,
            )
            return {
                "success": success and is_payment_successful(status),
                "payment_id": payment_id,
                "status": status,
                "raw": charge_raw,
                "init_raw": init_raw,
                "stage": "charge",
            }
        except Exception:
            pay_log.exception("Ошибка Charge order=%s", order_id)
            raise


async def get_payment_status(order_id: str) -> dict[str, Any]:
    """Проверка статуса платежа по order_id (CheckOrder)."""
    AsyncTKassaClient, _ = _import_tbank()
    async with _make_client(AsyncTKassaClient) as client:
        try:
            result = await client.check_order(order_id)
            return {
                "success": result.success,
                "status": result.status,
                "order_id": result.order_id,
                "payment_id": result.payment_id,
                "payments": result.payments,
                "raw": result.raw,
            }
        except Exception:
            pay_log.exception("Ошибка проверки статуса order=%s", order_id)
            raise


async def cancel_payment(payment_id: str, amount: int) -> dict[str, Any]:
    """Отмена/возврат платежа."""
    AsyncTKassaClient, _ = _import_tbank()
    from tbank_securepay import PaymentCancelParams  # type: ignore

    async with _make_client(AsyncTKassaClient) as client:
        try:
            result = await client.payment_cancel(
                PaymentCancelParams(payment_id=payment_id, amount=amount)
            )
            return {"success": result.success, "status": result.status, "raw": result.raw}
        except Exception:
            pay_log.exception("Ошибка отмены платежа payment_id=%s", payment_id)
            raise


def is_payment_successful(status: str | None) -> bool:
    """Платёж успешен (деньги получены или холд AUTHORIZED)."""
    return status in ("CONFIRMED", "AUTHORIZED")


async def refund_payment(payment_id: str, amount: int | None = None) -> dict[str, Any]:
    """Возврат средств через Cancel (для CONFIRMED = Refund в Т-Банке)."""
    AsyncTKassaClient, _ = _import_tbank()
    pay_log.info("Refund/Cancel payment_id=%s amount=%s", payment_id, amount)

    async with _make_client(AsyncTKassaClient) as client:
        try:
            body: dict[str, Any] = {"PaymentId": str(payment_id)}
            if amount is not None:
                body["Amount"] = int(amount)
            raw = await client.post("Cancel", body)
            success = bool(raw.get("Success", False))
            pay_log.info(
                "Refund result payment_id=%s success=%s status=%s error=%s",
                payment_id,
                success,
                raw.get("Status"),
                raw.get("Message") or raw.get("Details"),
            )
            return {
                "success": success,
                "status": raw.get("Status"),
                "payment_id": str(raw.get("PaymentId") or payment_id),
                "raw": raw,
            }
        except Exception:
            pay_log.exception("Ошибка refund payment_id=%s", payment_id)
            raise
