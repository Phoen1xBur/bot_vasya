"""Интеграция с Т-Банк (Т-Касса) через tbank-securepay.

- Создание платежа (payment_init)
- Верификация webhook (проверка подписи Token через append_token)
- Проверка статуса (get_state / check_order)
- Отмена/возврат (payment_cancel)
"""

import logging
from typing import Any

from shared.config import get_settings
from shared.logger import get_payment_logger

logger = logging.getLogger(__name__)
pay_log = get_payment_logger()

_settings = get_settings()

# Ленивый импорт библиотеки (может не быть при разработке без неё)
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


def _ssl_kwargs() -> dict:
    """SSL options for T-Bank client. Prefer system CA (Docker ca-certificates).

    Only disables verify when TBANK_SSL_VERIFY=false (gated env flag).
    """
    if _settings.TBANK_SSL_VERIFY:
        return {}
    import ssl
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "TBANK_SSL_VERIFY=false — TLS certificate verification DISABLED for T-Bank"
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {"ssl": ctx}


def _make_client(AsyncTKassaClient):
    kwargs = dict(
        terminal_key=_settings.TBANK_TERMINAL_ID,
        password=_settings.TBANK_TERMINAL_PASSWORD,
    )
    # tbank-securepay / underlying httpx may accept ssl / verify
    if not _settings.TBANK_SSL_VERIFY:
        kwargs["verify"] = False
    try:
        return AsyncTKassaClient(**kwargs)
    except TypeError:
        kwargs.pop("verify", None)
        return AsyncTKassaClient(**kwargs)


def verify_webhook_token(payload: dict[str, Any]) -> bool:
    """Проверка подписи webhook от Т-Банка.

    Т-Банк присылает POST с полями, включая Token.
    Пересчитываем Token по тем же правилам (append_token) и сравниваем.
    """
    try:
        _, append_token = _import_tbank()
        if not _settings.TBANK_TERMINAL_PASSWORD:
            logger.error("TBANK_TERMINAL_PASSWORD не задан — webhook не верифицируется")
            return False
        received_token = payload.get("Token", "")
        if not received_token:
            return False
        # Убираем Token, добавляем Password, считаем
        data = {k: v for k, v in payload.items() if k != "Token"}
        signed = append_token(data, _settings.TBANK_TERMINAL_PASSWORD)
        import hmac

        return hmac.compare_digest(signed.get("Token", ""), received_token)
    except Exception:
        logger.exception("Ошибка верификации webhook Т-Банка")
        return False


async def create_payment(
    amount: int,
    order_id: str,
    description: str,
    extra_data: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Создание платежа через Init.

    :param amount: сумма в копейках
    :param order_id: уникальный ID заказа
    :param description: описание
    :param extra_data: доп. поля DATA для заказа
    :return: dict с payment_url, payment_id, success
    """
    AsyncTKassaClient, _ = _import_tbank()
    pay_log.info("Создание платежа order=%s amount=%s", order_id, amount)

    async with _make_client(AsyncTKassaClient) as client:
        # Базовые параметры
        params_data = {
            "amount": amount,
            "order_id": order_id,
            "description": description,
        }
        if _settings.tbank_success_url:
            params_data["SUCCESS_URL"] = _settings.tbank_success_url
        if _settings.tbank_fail_url:
            params_data["FAILURL"] = _settings.tbank_fail_url
        if _settings.tbank_notification_url:
            params_data["NotificationURL"] = _settings.tbank_notification_url
        if extra_data:
            params_data["DATA"] = extra_data

        # Используем payment_init для плоских параметров, post — для вложенных DATA
        from tbank_securepay import PaymentInitParams  # type: ignore

        try:
            result = await client.payment_init(
                PaymentInitParams(
                    amount=amount,
                    order_id=order_id,
                    description=description,
                )
            )
            # Если нужны доп. поля (URL, DATA) — делаем сырой post с подписью
            if _settings.tbank_notification_url or extra_data or _settings.tbank_success_url:
                raw = await client.post(
                    "Init",
                    params_data,
                )
                return {
                    "success": raw.get("Success", False),
                    "payment_url": raw.get("PaymentURL"),
                    "payment_id": str(raw.get("PaymentId")) if raw.get("PaymentId") else None,
                    "order_id": raw.get("OrderId"),
                    "status": raw.get("Status"),
                    "raw": raw,
                }
            return {
                "success": result.success,
                "payment_url": result.payment_url,
                "payment_id": result.payment_id,
                "order_id": result.order_id,
                "status": result.status,
                "raw": result.raw,
            }
        except Exception:
            pay_log.exception("Ошибка создания платежа order=%s", order_id)
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
    """Платёж успешно завершён (деньги получены)."""
    return status == "CONFIRMED"


async def refund_payment(payment_id: str, amount: int | None = None) -> dict[str, Any]:
    """Возврат средств через Cancel (для CONFIRMED = Refund в Т-Банке).

    :param payment_id: PaymentId из Init/webhook
    :param amount: сумма возврата в копейках; None = полный возврат
    """
    AsyncTKassaClient, _ = _import_tbank()
    pay_log.info("Refund/Cancel payment_id=%s amount=%s", payment_id, amount)

    async with _make_client(AsyncTKassaClient) as client:
        try:
            # Сырой Cancel с PascalCase — надёжнее, чем typed wrapper для частичных возвратов
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

