"""Общие утилиты (без зависимости от aiogram-классов, где можно)."""

import random


def declension_word_by_number(number: int, word_form_0: str, word_form_1: str, word_form_2: str) -> str:
    """Склонение слова по числу.

    declension_word_by_number(1, 'васякоинов', 'васякоин', 'васякоина')
    'васякоин'
    declension_word_by_number(2, 'васякоинов', 'васякоин', 'васякоина')
    'васякоина'
    declension_word_by_number(5, 'васякоинов', 'васякоин', 'васякоина')
    'васякоинов'
    """
    if number % 10 == 1 and number % 100 != 11:
        return word_form_1
    if 1 < number % 10 < 5 and (number % 100 < 10 or number % 100 >= 20):
        return word_form_2
    return word_form_0


def vasya_coin_word(number: int) -> str:
    """Склонение слова «васякоин»."""
    return declension_word_by_number(number, "васякоинов", "васякоин", "васякоина")


def weighted_choice(items: list[tuple[object, float]]):
    """Выбор элемента по весам: [(item, weight), ...]."""
    total = sum(w for _, w in items)
    r = random.random() * total
    upto = 0.0
    for item, w in items:
        if upto + w >= r:
            return item
        upto += w
    return items[-1][0]
