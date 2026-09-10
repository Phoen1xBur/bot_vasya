from . import common, groups, private, chat_member
from src.handlers.groups import group_routers
from .callback import routers as callback_routers

routers = callback_routers + group_routers + [
    private.router,
    chat_member.router,
    common.router,
]
