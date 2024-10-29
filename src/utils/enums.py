from enum import Enum, unique


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
