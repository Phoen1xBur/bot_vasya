import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

"""Модели предметной области.

Порядок импорта важен для relationship-связей.
"""

from shared.models.user import UserOrm
from shared.models.chat import TelegramChatOrm
from shared.models.group_user import GroupUserOrm
from shared.models.message import MessageOrm
from shared.models.money import ProfessionOrm, TransactionOrm, Prison
from shared.models.payment import PaymentOrm
from shared.models.subscription import SubscriptionOrm
from shared.models.donation import DonationOrm
from shared.models.order import OrderOrm
from shared.models.ad_campaign import AdCampaignOrm, ChatUniqueUsersOrm
from shared.models.game_room import GameRoomOrm, GameParticipantOrm

__all__ = [
    "UserOrm",
    "TelegramChatOrm",
    "GroupUserOrm",
    "MessageOrm",
    "ProfessionOrm",
    "TransactionOrm",
    "Prison",
    "PaymentOrm",
    "SubscriptionOrm",
    "DonationOrm",
    "OrderOrm",
    "AdCampaignOrm",
    "ChatUniqueUsersOrm",
    "GameRoomOrm",
    "GameParticipantOrm",
]
