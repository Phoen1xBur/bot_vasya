"""Ответ пользователя реплаем на сообщение notify-bus (captcha/код) -> сервису через шину."""
import logging
import time

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router(name="notify_reply")


class PendingNotifyReply(BaseFilter):
    """Пропускает только реплаи на сообщения, для которых Вася ждёт ответ (иначе — дальше по роутерам)."""

    async def __call__(self, message: Message) -> bool | dict:
        from messaging.notify_bus import get_consumer

        reply = message.reply_to_message
        consumer = get_consumer()
        if reply is None or consumer is None or message.from_user is None:
            return False
        # Только адресат: ключ содержит id чата, получатель = chat_id
        ctx = await consumer.pop_reply_context(message.chat.id, reply.message_id)
        if not ctx or ctx.get("user_id") != str(message.from_user.id):
            return False
        return {"notify_ctx": ctx, "notify_consumer": consumer}


@router.message(F.chat.type == "private", F.text, PendingNotifyReply())
async def on_notify_reply(message: Message, notify_ctx: dict, notify_consumer) -> None:
    reply = message.reply_to_message
    if int(notify_ctx.get("expires_at", "0")) < time.time():
        await notify_consumer.finish_reply(message.chat.id, reply.message_id)
        await message.reply("Ответ опоздал: время ожидания вышло, запрос уже закрыт.")
        return
    ok = await notify_consumer.publish_reply(notify_ctx, message.text.strip())
    if ok:
        await notify_consumer.finish_reply(message.chat.id, reply.message_id)
        await message.reply("Передал ✅")
    else:
        logger.warning("notify reply not delivered corr=%s", notify_ctx.get("correlation_id"))
        await message.reply("Не смог передать (шина недоступна), попробуй ответить ещё раз.")
