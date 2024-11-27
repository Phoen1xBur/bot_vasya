from . import common, groups, private, chat_member
from callback import routers as callback_routers

routers = [
    common.router,
    groups.router,
    private.router,
    chat_member.router,
].extend(callback_routers)
