from . import auto_delete_message, redis_context

middlewares = [
    redis_context.AddRedisContext(),
]
