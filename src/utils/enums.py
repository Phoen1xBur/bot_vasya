from enum import Enum, unique
import random

from aiogram.enums import *  # noqa


@unique
class Rank(Enum):
    USER = 'user'
    VIP = 'vip'
    PREMIUM = 'premium'
    OWNER = 'owner'


@unique
class TransactionType(Enum):
    # Получение средств путем
    WORK = 'work'  # работы
    ROB = 'rob'  # кражи
    TAX_AND_FINE = 'tax_and_fine'  # налоги и штрафы (только выплаты от пользователя)
    USER_TRANSFER = 'user_transfer'  # передачи денег между пользователями
    BANK_TRANSFER = 'bank_transfer'  # передачи денег между банком и пользователем (и наоборот(выплата))


class RandomRob(Enum):
    SUCCESS = 'SUCCESS'
    FAIL = 'FAIL'
    POLICE = 'POLICE'


class EnumChance:
    def __init__(self, variant: Enum, percent: float):
        self.enum = variant
        self.percent = percent / 100 if percent > 1 else percent

    @staticmethod
    def get_percent(self: "EnumChance"):
        return self.percent

