from aiogram.types import URLInputFile
from aiogram.methods import SendMessage, SendPhoto

from shared.bot_identity import help_mention
from shared.config import HELP_TEXT


class CommandUndefined(SendMessage):
    def __init__(self, chat_id: int):
        super().__init__(
            chat_id=chat_id,
            text=(
                "Я ничего не понял, что ты хочешь от меня\n"
                f"Можешь написать {help_mention()} для справки"
            ),
        )


class CommandStart(SendMessage):
    text: str = (
        "Привет! Я бот Вася, создан для разнообразия ваших бесед в группах. АЛЁ\n"
        "Добавляй меня скорее! Команды: /help"
    )

    def __init__(self, chat_id: int):
        super().__init__(chat_id=chat_id)


class CommandHelp(SendMessage):
    text: str = HELP_TEXT

    def __init__(self, chat_id: int):
        super().__init__(chat_id=chat_id)


class CommandCat(SendPhoto):
    caption: str = "Держи котика"

    def __init__(self, chat_id: int, text: list[str] | None = None):
        url = "https://cataas.com/cat"
        if text:
            url = "https://cataas.com/cat/says/" + " ".join(text) + "?fontSize=50&fontColor=white"
        photo = URLInputFile(url)
        super().__init__(chat_id=chat_id, photo=photo)
