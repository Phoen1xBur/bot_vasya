from . import auto_delete_message, redis_context, chat_settings

middlewares = [
    redis_context.AddRedisContext(),
    chat_settings.ChatSettingsMiddleware()
]
