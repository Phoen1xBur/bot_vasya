import asyncio
import time
import redis as redis_package
from aiogram import Bot

REDIS_KEY = "bot:auto_delete"


class AutoDeleteService:
    def __init__(self, redis: redis_package.Redis, bot: Bot):
        self.redis = redis
        self.bot = bot

    def schedule(self, chat_id: int, message_id: int, delay: int = 60):
        delete_at = int(time.time()) + delay
        # zset: score = время удаления
        self.redis.zadd(
            REDIS_KEY,
            {f"{chat_id}:{message_id}": delete_at}
        )

    async def run_cleaner(self, interval: int = 5):
        """Фоновая задача для удаления просроченных сообщений"""
        while True:
            now = int(time.time())
            expired = self.redis.zrangebyscore(REDIS_KEY, "-inf", now)

            if expired:
                for item in expired:
                    chat_id, msg_id = map(int, item.split(":"))
                    try:
                        await self.bot.delete_message(chat_id, msg_id)
                    except Exception as e:
                        print(e)
                # удалить из redis
                self.redis.zremrangebyscore(REDIS_KEY, "-inf", now)

            await asyncio.sleep(interval)
