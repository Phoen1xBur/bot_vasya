from aiogram import BaseMiddleware

from shared.redis_client import get_redis


class AddRedisContext(BaseMiddleware):
    async def __call__(self, handler, event, data):
        data["redis"] = get_redis()
        return await handler(event, data)