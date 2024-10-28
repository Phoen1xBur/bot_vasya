from enum import Enum, unique


@unique
class Rank(Enum):
    USER = 'user'
    VIP = 'vip'
    PREMIUM = 'premium'
