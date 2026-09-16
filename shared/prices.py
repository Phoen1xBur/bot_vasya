"""Цены и флаги из Redis (админка) с fallback на дефолты в коде."""

from __future__ import annotations

import logging
from typing import Any

from shared.enums import SubscriptionTier
from shared.models.subscription import TIER_PRICES_KOPECKS
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)

# Ключи совпадают с админкой /api/admin/prices
PRICE_KEYS: dict[str, str] = {
    "sub_vip": "price:sub:vip",
    "sub_premium": "price:sub:premium",
    "sub_elite": "price:sub:elite",
    "ad_per_1000": "price:ad:per_1000",
    "ai_check_enabled": "config:ad:ai_check",
}

_TIER_TO_ADMIN_KEY = {
    SubscriptionTier.VIP: "sub_vip",
    SubscriptionTier.PREMIUM: "sub_premium",
    SubscriptionTier.ELITE: "sub_elite",
}

DEFAULT_AD_PER_1000 = 1000_00
DEFAULT_AI_CHECK_ENABLED = True


def _redis_get(key: str) -> str | None:
    try:
        val = get_redis().get(key)
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return str(val)
    except Exception:
        logger.exception("Redis get failed for %s", key)
        return None


def get_tier_price_kopecks(tier: SubscriptionTier) -> int | None:
    """Цена тарифа в копейках: Redis → иначе TIER_PRICES_KOPECKS. FREE → None."""
    admin_key = _TIER_TO_ADMIN_KEY.get(tier)
    if admin_key is None:
        return None
    raw = _redis_get(PRICE_KEYS[admin_key])
    if raw is not None and str(raw).strip() != "":
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning("Bad redis price for %s: %r", admin_key, raw)
    return TIER_PRICES_KOPECKS.get(tier)


def get_ad_price_per_1000_kopecks() -> int:
    raw = _redis_get(PRICE_KEYS["ad_per_1000"])
    if raw is not None and str(raw).strip() != "":
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning("Bad redis ad_per_1000: %r", raw)
    return DEFAULT_AD_PER_1000


def is_ad_ai_check_enabled() -> bool:
    raw = _redis_get(PRICE_KEYS["ai_check_enabled"])
    if raw is None:
        return DEFAULT_AI_CHECK_ENABLED
    s = str(raw).strip().lower()
    if s in ("0", "false", "no", "off", ""):
        return False
    if s in ("1", "true", "yes", "on"):
        return True
    return DEFAULT_AI_CHECK_ENABLED


def get_admin_prices_snapshot() -> dict[str, Any]:
    """Снимок всех админ-цен (как /api/admin/prices)."""
    defaults: dict[str, Any] = {
        "sub_vip": TIER_PRICES_KOPECKS[SubscriptionTier.VIP],
        "sub_premium": TIER_PRICES_KOPECKS[SubscriptionTier.PREMIUM],
        "sub_elite": TIER_PRICES_KOPECKS[SubscriptionTier.ELITE],
        "ad_per_1000": DEFAULT_AD_PER_1000,
        "ai_check_enabled": "true" if DEFAULT_AI_CHECK_ENABLED else "false",
    }
    result: dict[str, Any] = {}
    for key, redis_key in PRICE_KEYS.items():
        raw = _redis_get(redis_key)
        if raw is not None:
            result[key] = raw
        else:
            result[key] = defaults[key]
    return result
