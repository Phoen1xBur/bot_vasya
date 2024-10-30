from . import common, groups, private, chat_member

routers = [
    common.router,
    groups.router,
    private.router,
    chat_member.router,
]
