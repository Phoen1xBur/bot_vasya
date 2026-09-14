"""Message bus between bot and API services."""

from .rabbitmq import MessageBus, get_bus

__all__ = ["MessageBus", "get_bus"]
