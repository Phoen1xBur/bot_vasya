from aiogram.types import Message
from random import random
from models import ChatGroupSettings
import aiohttp


async def set_chance(message: Message, chance: int):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    try:
        chance = int(chance)
        if chance > 100 or chance < 0:
            raise ValueError
        answer = f'Шанс сообщения изменен на {chance}'
        await ChatGroupSettings.change_answer_chance(message.chat.id, chance)
    except ValueError:
        answer = 'Шанс должен быть числом от 0 до 100'

    return answer


def choice(words):
    answer = 'Непредвиденная ошибка. Обратитесь в тех. поддержку'

    words_lower = list(map(lambda text: text.lower(), words))

    count_or = words_lower.count('или')

    if count_or == 0 or count_or > 1:
        return 'В предложении должен присутствовать один выбор посредством ИЛИ'

    if words_lower[0] == 'или' or words_lower[-1] == 'или':
        return 'Выбор ИЛИ не должен находится в начале или конце'

    index_or = words_lower.index('или')
    answer = ' '.join(words[:index_or] if random() < .5 else words[index_or + 1:])

    return answer


async def yesno() -> tuple:
    url = 'https://yesno.wtf/api'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            json = await response.json()
    animation, answer_en = json['image'], json['answer']
    match answer_en:
        case 'yes':
            answer_ru = 'Да'
        case 'no':
            answer_ru = 'Нет'
        case 'maybe':
            answer_ru = 'Может быть'
        case _:
            answer_ru = 'Спроси позже...'
    return animation, answer_ru
