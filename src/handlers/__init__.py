from . import common, private, chat_member
from .groups import group_routers
from .callback import routers as callback_routers

routers = callback_routers + group_routers + [
    private.router,
    chat_member.router,
    common.router,
]
