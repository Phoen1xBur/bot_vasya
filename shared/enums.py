"""Enum'ы проекта."""
from __future__ import annotations

from enum import Enum, unique

from aiogram.enums import *  # noqa: F401,F403  — реэкспорт aiogram-енумов


@unique
class Rank(Enum):
    USER = "user"
    VIP = "vip"
    PREMIUM = "premium"
    OWNER = "owner"


@unique
class SubscriptionTier(Enum):
    """Уровни платной подписки."""
    FREE = "free"
    VIP = "vip"
    PREMIUM = "premium"
    ELITE = "elite"


@unique
class TransactionType(Enum):
    WORK = "work"
    ROB = "rob"
    TAX_AND_FINE = "tax_and_fine"
    USER_TRANSFER = "user_transfer"
    BANK_TRANSFER = "bank_transfer"
    GAME_WIN = "game_win"
    GAME_LOSS = "game_loss"
    DONATE_BONUS = "donate_bonus"
    GAME_COMMISSION = "game_commission"


@unique
class RandomRob(Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    POLICE = "POLICE"


@unique
class PaymentType(Enum):
    SUBSCRIPTION = "subscription"
    DONATION = "donation"
    ORDER = "order"
    AD_CAMPAIGN = "ad_campaign"


@unique
class PaymentStatus(Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"
    PARTIAL_REFUNDED = "PARTIAL_REFUNDED"
    CANCELLED = "CANCELLED"
    DEADLINE_EXPIRED = "DEADLINE_EXPIRED"


@unique
class SubscriptionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


@unique
class AdCampaignStatus(Enum):
    DRAFT = "draft"
    AI_PENDING = "ai_pending"
    AI_APPROVED = "ai_approved"
    AI_REJECTED = "ai_rejected"
    ADMIN_PENDING = "admin_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


@unique
class GameType(Enum):
    TTT = "ttt"          # крестики-нолики (дуэль 1×1)
    ROULETTE = "roulette"
    SLOTS = "slots"      # слот-машина


@unique
class GameRoomStatus(Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class EnumChance:
    """Взвешенный выбор из Enum'ов (для кражи)."""

    def __init__(self, variant: Enum, percent: float):
        self.enum = variant
        self.percent = percent / 100 if percent > 1 else percent

    @staticmethod
    def get_percent(self: "EnumChance"):
        return self.percent
