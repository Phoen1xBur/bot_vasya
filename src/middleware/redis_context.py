from aiogram import BaseMiddleware

from config import redis


class AddRedisContext(BaseMiddleware):
    async def __call__(self, handler, event, data):
        data["redis"] = redis
        return await handler(event, data)
