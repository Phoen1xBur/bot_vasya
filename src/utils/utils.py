import random

import markovify
from mistralai.client.models import ChatCompletionResponse

from config import settings, mistral


def generate_text(messages: list[str]) -> str:
    if messages:
        text_model = markovify.NewlineText('\n'.join(messages), state_size=1, well_formed=False)
        msg_text = text_model.make_short_sentence(max_chars=4096, tries=100) or random.choice(messages)
        return msg_text
    return 'У меня пока слишком мало информации о вас!!'


async def generate_text_from_ai(messages: list[dict[str, str]]) -> ChatCompletionResponse:
    if messages:
        model = settings.MISTRAL_MODEL
        chat_response = await mistral.chat.complete_async(model=model, messages=messages)
        return chat_response
    return 'У меня пока слишком мало информации о вас!!'

