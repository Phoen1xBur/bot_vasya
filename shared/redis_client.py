"""Синглтон Redis-клиент для обоих сервисов."""

import redis as redis_package

from shared.config import get_settings

_redis: redis_package.Redis | None = None


def get_redis() -> redis_package.Redis:
    global _redis
    if _redis is None:
        _redis = redis_package.Redis(**get_settings().REDIS_CREDENTIALS)
    return _redis
