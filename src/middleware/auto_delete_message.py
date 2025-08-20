from aiogram import BaseMiddleware

from utils.auto_delete_message_service import AutoDeleteService


class AutoDeleteMiddleware(BaseMiddleware):
    def __init__(self, auto_delete_service: AutoDeleteService):
        self.message_delete_service = auto_delete_service

    async def __call__(self, handler, event, data):
        data["message_delete_service"] = self.message_delete_service
        return await handler(event, data)
