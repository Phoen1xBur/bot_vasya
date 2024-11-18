from enum import Enum, unique

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
