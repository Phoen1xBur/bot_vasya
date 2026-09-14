from . import minigames, minigames_ttt, profile, rob_police, subscribe_donate

routers = [
    minigames.router,
    minigames_ttt.router,
    profile.router,
    rob_police.router,
    subscribe_donate.router,
]
