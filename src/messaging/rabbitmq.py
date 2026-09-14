"""RabbitMQ bus for bot ↔ API communication.

Bot and FastAPI run as separate processes and exchange events via this bus.
If RabbitMQ is unavailable, publish/consume degrade gracefully so the bot
keeps working without the API service.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class MessageBus:
    def __init__(self, url: str, exchange_name: str = "vasya.bus") -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._connection = None
        self._channel = None
        self._exchange = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        try:
            import aio_pika
            from aio_pika import ExchangeType

            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            self._connected = True
            logger.info("RabbitMQ connected: exchange=%s", self._exchange_name)
            return True
        except Exception:
            self._connected = False
            logger.warning(
                "RabbitMQ unavailable (%s) — bus disabled until reconnect",
                self._url,
                exc_info=True,
            )
            return False

    async def close(self) -> None:
        self._connected = False
        try:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
        except Exception:
            logger.exception("Error closing RabbitMQ connection")
        finally:
            self._connection = None
            self._channel = None
            self._exchange = None

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> bool:
        """Publish JSON event. Returns False if bus is down."""
        if not self._connected or self._exchange is None:
            return False
        try:
            import aio_pika

            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            message = aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self._exchange.publish(message, routing_key=routing_key)
            return True
        except Exception:
            logger.exception("Failed to publish to %s", routing_key)
            return False

    async def consume(
        self,
        queue_name: str,
        binding_keys: list[str],
        handler: EventHandler,
    ) -> None:
        """Bind a durable queue and dispatch messages to handler forever."""
        if not self._connected or self._channel is None or self._exchange is None:
            logger.warning("Cannot consume %s: bus not connected", queue_name)
            return

        queue = await self._channel.declare_queue(queue_name, durable=True)
        for key in binding_keys:
            await queue.bind(self._exchange, routing_key=key)

        logger.info("Consuming queue=%s keys=%s", queue_name, binding_keys)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        payload = json.loads(message.body.decode("utf-8"))
                        await handler(message.routing_key or "", payload)
                    except Exception:
                        logger.exception(
                            "Error handling message key=%s", message.routing_key
                        )


_bus: Optional[MessageBus] = None


def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        from config import settings

        _bus = MessageBus(settings.RABBITMQ_URL, settings.RABBITMQ_EXCHANGE)
    return _bus


async def ensure_bus() -> MessageBus:
    bus = get_bus()
    if not bus.connected:
        await bus.connect()
    return bus
