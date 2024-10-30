from enum import Enum, unique

from aiogram.enums import *  # noqa


@unique
class Rank(Enum):
    USER = 'user'
    VIP = 'vip'
    PREMIUM = 'premium'


class AnswerType(Enum):
    Text = 'text'
    Photo = 'photo'
    Video = 'video'
    Animation = 'animation'
    Nope = None
