from . import auto_delete_message, chat_settings, redis_context

middlewares = [
    redis_context.AddRedisContext(),
    chat_settings.ChatSettingsMiddleware(),
]
