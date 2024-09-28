import random

import markovify

from database import sync_engine, Base
from models import Messages


def create_tables():
    # Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


def generate_text(messages: list[str]) -> str:
    text_model = markovify.NewlineText('\n'.join(messages), state_size=1, well_formed=False)
    msg_text = text_model.make_short_sentence(max_chars=4096, tries=100) or random.choice(messages)
    return msg_text
