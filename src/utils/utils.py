import random

import markovify


def generate_text(messages: list[str]) -> str:
    if messages:
        text_model = markovify.NewlineText('\n'.join(messages), state_size=1, well_formed=False)
        msg_text = text_model.make_short_sentence(max_chars=4096, tries=100) or random.choice(messages)
        return msg_text
    return 'У меня пока слишком мало информации о вас!!'

