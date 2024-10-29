import random

import markovify

from database import sync_engine, Base


def create_tables():
    # Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)
    # Base.metadata.reflect(bind=sync_engine, extend_existing=True)


def generate_text(messages: list[str]) -> str:
    if messages:
        text_model = markovify.NewlineText('\n'.join(messages), state_size=1, well_formed=False)
        msg_text = text_model.make_short_sentence(max_chars=4096, tries=100) or random.choice(messages)
        return msg_text
    return 'У меня пока слишком мало информации о вас!!'

