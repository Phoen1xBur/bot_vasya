from . import common, groups, groups_voice, private, chat_member
from .callback import routers as callback_routers

routers = callback_routers + [
    groups.router,
    groups_voice.router,
    private.router,
    chat_member.router,
    common.router,
]
