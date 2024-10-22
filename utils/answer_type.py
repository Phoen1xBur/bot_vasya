from enum import Enum


class AnswerType(Enum):
    Text = 'text'
    Photo = 'photo'
    Video = 'video'
    Animation = 'animation'
    Nope = None
