"""Шина сообщений bot ↔ API (RabbitMQ).

Если RabbitMQ недоступен — бот продолжает работать без шины.
"""
from shared.messaging import MessageBus, ensure_bus, get_bus  # noqa: F401
