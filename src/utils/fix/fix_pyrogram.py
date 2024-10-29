from pyrogram import utils


def get_peer_type_new(peer_id: int) -> str:
    """
    Суть:
        В pyrogram.utils есть метод get_peer_type, который неправильно проверяет тип чата(чат/группа/канал),
        относительно его peer_id
    Решение:
        Переделать метод, и переприсвоить его для решения проблемы
    """
    peer_id_str = str(peer_id)
    if not peer_id_str.startswith("-"):
        return "user"
    elif peer_id_str.startswith("-100"):
        return "channel"
    else:
        return "chat"


utils.get_peer_type = get_peer_type_new
