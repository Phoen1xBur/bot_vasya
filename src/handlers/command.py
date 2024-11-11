from aiogram.types import URLInputFile
from aiogram.methods import SendMessage, SendPhoto

from config import help_text


class CommandUndefined(SendMessage):
    text: str = 'Я ничего не понял, что ты хочешь от меня\nМожешь написать /help@vasya_fun_bot для справки'

    def __init__(self, chat_id: int):
        super().__init__(chat_id=chat_id)


class CommandStart(SendMessage):
    text: str = ('Привет! Я бот Вася, и я создан для разнообразия ваших бесед в группах.\n'
                 'Добавляй меня скорее!')

    def __init__(self, chat_id: int):
        super().__init__(chat_id=chat_id)


class CommandHelp(SendMessage):
    text: str = help_text

    def __init__(self, chat_id: int):
        super().__init__(chat_id=chat_id)


class CommandCat(SendPhoto):
    caption: str = 'Держи котика'

    def __init__(self, chat_id: int, text: list[str] = None):
        url = 'https://cataas.com/cat'
        if text:
            url = 'https://cataas.com/cat/says/' + ' '.join(text) + '?fontSize=50&fontColor=white'
        photo = URLInputFile(url)
        super().__init__(chat_id=chat_id, photo=photo)
