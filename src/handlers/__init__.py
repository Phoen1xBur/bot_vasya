from . import common, private, chat_member, notify_reply
from .groups import group_routers
from .callback import routers as callback_routers

routers = [notify_reply.router] + callback_routers + group_routers + [
    private.router,
    chat_member.router,
    common.router,
]
