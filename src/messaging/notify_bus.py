"""Внешняя шина уведомлений: любой сервис -> Telegram через Васю.

Отдельный брокер (amqps, vhost /notify), очередь notify.vasya привязана к
exchange ``notify`` по ключу ``send.#``. Внутренняя шина Васи (vasya.bus)
не затрагивается. Если брокер недоступен, бот работает как обычно, а
потребитель переподключается с экспоненциальной паузой.

Формат сообщения (JSON):
    {"user_id": 123 | "user_ids": [1, 2], "text": "...", "source": "school",
     "level": "info|warn|error", "parse_mode": "HTML|MarkdownV2" | null,
     "correlation_id": "..."}
Если получатель не указан — шлём админу (NOTIFY_DEFAULT_USER_ID).
Если есть correlation_id (или AMQP correlation_id / reply_to) — публикуем отчёт
в exchange ``notify`` с ключом ``report.<source>``.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from collections import defaultdict, deque
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)

logger = logging.getLogger("notify_bus")

QUEUE = "notify.vasya"
LEVEL_ICON = {"info": "ℹ️", "warn": "⚠️", "error": "🚨"}
UNREACHABLE_MARKERS = ("chat not found", "user is deactivated", "peer_id_invalid", "bot was blocked")
MAX_ATTEMPTS = 3
MAX_REPORT_FAILED = 200


class Throttle:
    """Глобально ~GLOBAL_RATE msg/s и не чаще 1 msg/s в один чат."""

    def __init__(self, global_rate: float = 25.0, per_chat_interval: float = 1.0) -> None:
        self._gap = 1.0 / global_rate
        self._per_chat = per_chat_interval
        self._next_global = 0.0
        self._last_chat: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, chat_id: int) -> None:
        async with self._lock:
            now = time.monotonic()
            at = max(now, self._next_global, self._last_chat.get(chat_id, 0.0) + self._per_chat)
            self._next_global = at + self._gap
            self._last_chat[chat_id] = at
            if len(self._last_chat) > 20000:
                self._last_chat = {k: v for k, v in self._last_chat.items() if v > now - 5}
        delay = at - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)


class SourceLimiter:
    """Лимиты на источник: сообщений в минуту и получателей в час."""

    def __init__(self, max_msgs_per_min: int, max_recipients_per_hour: int) -> None:
        self._msgs: dict[str, deque[float]] = defaultdict(deque)
        self._rcpts: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
        self._max_msgs = max_msgs_per_min
        self._max_rcpts = max_recipients_per_hour

    def allow(self, source: str, recipients: int) -> str | None:
        now = time.monotonic()
        m = self._msgs[source]
        while m and m[0] < now - 60:
            m.popleft()
        r = self._rcpts[source]
        while r and r[0][0] < now - 3600:
            r.popleft()
        if len(m) >= self._max_msgs:
            return f"rate limit: >{self._max_msgs} сообщений/мин"
        if sum(n for _, n in r) + recipients > self._max_rcpts:
            return f"rate limit: >{self._max_rcpts} получателей/час"
        m.append(now)
        r.append((now, recipients))
        return None


class NotifyConsumer:
    def __init__(self, bot: Bot, settings: Any, redis_factory: Any) -> None:
        self.bot = bot
        self.url: str = settings.NOTIFY_AMQP_URL
        self.exchange_name: str = settings.NOTIFY_EXCHANGE
        self.default_user: int = settings.NOTIFY_DEFAULT_USER_ID
        self.max_text: int = settings.NOTIFY_MAX_TEXT
        self.max_rcpts: int = settings.NOTIFY_MAX_RECIPIENTS
        self.unreach_ttl: int = settings.NOTIFY_UNREACHABLE_TTL_SEC
        self.throttle = Throttle()
        self.limiter = SourceLimiter(
            settings.NOTIFY_SOURCE_MAX_MSGS_PER_MIN, settings.NOTIFY_SOURCE_MAX_RECIPIENTS_PER_HOUR
        )
        self._redis_factory = redis_factory
        self._redis: Any = None
        self._exchange: Any = None

    # ---------- Redis: недостижимые получатели ----------
    def _r(self) -> Any:
        if self._redis is None:
            self._redis = self._redis_factory()
        return self._redis

    async def _is_unreachable(self, uid: int) -> bool:
        try:
            return bool(await self._r().exists(f"notify:unreachable:{uid}"))
        except Exception:  # redis недоступен — не блокируем отправку
            logger.warning("redis exists failed", exc_info=True)
            return False

    async def _mark_unreachable(self, uid: int, reason: str) -> None:
        try:
            await self._r().set(f"notify:unreachable:{uid}", reason[:200], ex=self.unreach_ttl)
        except Exception:
            logger.warning("redis set failed", exc_info=True)

    # ---------- Отправка одному получателю ----------
    async def _send_one(self, uid: int, text: str, parse_mode: str | None) -> tuple[bool, str]:
        """Возвращает (успех, причина). Исключения наружу не выпускает."""
        pm = parse_mode
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await self.throttle.wait(uid)
            try:
                await self.bot.send_message(uid, text, parse_mode=pm)
                return True, "ok"
            except TelegramRetryAfter as e:
                logger.warning("retry_after %ss uid=%s", e.retry_after, uid)
                await asyncio.sleep(e.retry_after + 0.5)
            except TelegramForbiddenError as e:
                await self._mark_unreachable(uid, f"forbidden: {e.message}")
                logger.info("uid=%s unreachable (forbidden): %s", uid, e.message)
                return False, "forbidden"
            except TelegramMigrateToChat:
                return False, "migrated"
            except TelegramBadRequest as e:
                msg = (e.message or "").lower()
                if any(mk in msg for mk in UNREACHABLE_MARKERS):
                    await self._mark_unreachable(uid, f"bad_request: {e.message}")
                    logger.info("uid=%s unreachable: %s", uid, e.message)
                    return False, "chat_not_found"
                if "parse entities" in msg and pm is not None:
                    pm = None  # разметка кривая — пробуем простым текстом
                    continue
                logger.warning("bad request uid=%s: %s", uid, e.message)
                return False, f"bad_request: {e.message[:80]}"
            except (TelegramNetworkError, TelegramServerError) as e:
                logger.warning("network/server error uid=%s attempt=%s: %s", uid, attempt, e)
                await asyncio.sleep(min(2 ** attempt, 15))
        return False, "retries_exhausted"

    # ---------- Обработка сообщения ----------
    @staticmethod
    def _ids(payload: dict[str, Any], default: int) -> list[int]:
        raw: list[Any] = []
        if payload.get("user_ids") is not None:
            if not isinstance(payload["user_ids"], list):
                raise ValueError("user_ids must be a list")
            raw.extend(payload["user_ids"])
        if payload.get("user_id") is not None:
            raw.append(payload["user_id"])
        if not raw:
            raw = [default]
        ids: list[int] = []
        for x in raw:
            if isinstance(x, bool) or not isinstance(x, (int, str)):
                raise ValueError(f"bad user id {x!r}")
            ids.append(int(x))
        return list(dict.fromkeys(ids))

    async def _report(self, source: str, corr: str, data: dict[str, Any]) -> None:
        if self._exchange is None:
            return
        import aio_pika

        body = json.dumps({"correlation_id": corr, "source": source, **data}, ensure_ascii=False)
        try:
            await self._exchange.publish(
                aio_pika.Message(body=body.encode(), content_type="application/json", correlation_id=corr or None),
                routing_key=f"report.{source}",
            )
        except Exception:
            logger.warning("report publish failed", exc_info=True)

    async def handle(self, routing_key: str, body: bytes, amqp_corr: str | None, reply_to: str | None) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            text = payload.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("text required")
            src_raw = payload.get("source") or routing_key.removeprefix("send.") or "unknown"
            source = "".join(c for c in str(src_raw) if c.isalnum() or c in "-_.")[:40] or "unknown"
            ids = self._ids(payload, self.default_user)
        except (ValueError, UnicodeDecodeError, TypeError) as e:
            logger.warning("notify: отброшено невалидное сообщение key=%s: %s", routing_key, e)
            return

        corr = str(payload.get("correlation_id") or amqp_corr or reply_to or "")
        want_report = bool(corr)
        if len(ids) > self.max_rcpts:
            logger.warning("notify: source=%s слишком много получателей (%s)", source, len(ids))
            if want_report:
                await self._report(source, corr, {"status": "rejected", "reason": "too many recipients", "total": len(ids)})
            return
        denied = self.limiter.allow(source, len(ids))
        if denied:
            logger.warning("notify: source=%s отклонено: %s", source, denied)
            if want_report:
                await self._report(source, corr, {"status": "rejected", "reason": denied, "total": len(ids)})
            return

        pm = payload.get("parse_mode")
        if pm not in ("HTML", "MarkdownV2", "Markdown"):
            pm = None
        icon = LEVEL_ICON.get(str(payload.get("level", "info")), "")
        label = html.escape(source) if pm == "HTML" else source
        if pm == "MarkdownV2":
            label = "".join("\\" + c if c in "_*[]()~`>#+-=|{}.!" else c for c in source)
        full = f"{icon} [{label}] {text}".strip()
        if len(full) > self.max_text:
            full = full[: self.max_text - 1] + "…"

        sent, skipped = 0, 0
        failed: list[dict[str, Any]] = []
        for uid in ids:
            if await self._is_unreachable(uid):
                skipped += 1
                continue
            try:
                ok, reason = await self._send_one(uid, full, pm)
            except Exception:  # один получатель не должен валить партию
                logger.exception("notify: неожиданная ошибка uid=%s", uid)
                ok, reason = False, "internal_error"
            if ok:
                sent += 1
            else:
                failed.append({"user_id": uid, "reason": reason})
        logger.info("notify: source=%s total=%s sent=%s skipped_unreachable=%s failed=%s",
                    source, len(ids), sent, skipped, len(failed))
        if want_report:
            await self._report(source, corr, {
                "status": "done", "total": len(ids), "sent": sent,
                "skipped_unreachable": skipped, "failed_count": len(failed),
                "failed": failed[:MAX_REPORT_FAILED],
            })

    # ---------- Подключение ----------
    async def run(self) -> None:
        if not self.url:
            logger.info("NOTIFY_AMQP_URL не задан — внешняя шина отключена")
            return
        import aio_pika

        backoff = 5
        while True:
            conn = None
            try:
                conn = await aio_pika.connect_robust(self.url, timeout=15)
                channel = await conn.channel()
                await channel.set_qos(prefetch_count=1)
                self._exchange = await channel.get_exchange(self.exchange_name, ensure=False)
                queue = await channel.get_queue(QUEUE, ensure=False)
                logger.info("notify bus connected, queue=%s", QUEUE)
                backoff = 5
                async with queue.iterator() as it:
                    async for message in it:
                        # requeue=False: при падении сообщение не зацикливается
                        async with message.process(requeue=False, ignore_processed=True):
                            try:
                                await self.handle(message.routing_key or "", message.body,
                                                  message.correlation_id, message.reply_to)
                            except Exception:
                                logger.exception("notify: ошибка обработки, сообщение отброшено")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("notify bus недоступна (%s: %s), повтор через %ss", type(e).__name__, e, backoff)
            finally:
                self._exchange = None
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:
                        logger.debug("notify conn close failed", exc_info=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)
