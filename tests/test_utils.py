"""Тесты общих утилит (чистая логика, без БД)."""
from shared.utils import declension_word_by_number, vasya_coin_word, weighted_choice


def test_declension_word_by_number():
    f = ("васякоинов", "васякоин", "васякоина")
    assert declension_word_by_number(1, *f) == "васякоин"
    assert declension_word_by_number(2, *f) == "васякоина"
    assert declension_word_by_number(3, *f) == "васякоина"
    assert declension_word_by_number(5, *f) == "васякоинов"
    assert declension_word_by_number(11, *f) == "васякоинов"
    assert declension_word_by_number(21, *f) == "васякоин"
    assert declension_word_by_number(25, *f) == "васякоинов"
    assert declension_word_by_number(0, *f) == "васякоинов"


def test_vasya_coin_word():
    assert vasya_coin_word(1) == "васякоин"
    assert vasya_coin_word(2) == "васякоина"
    assert vasya_coin_word(100) == "васякоинов"


def test_weighted_choice_single():
    assert weighted_choice([("a", 1.0)]) == "a"


def test_weighted_choice_zero_weight():
    # весь вес на b — всегда b
    assert weighted_choice([("a", 0.0), ("b", 1.0)]) == "b"


def test_weighted_choice_distribution():
    from collections import Counter

    samples = [weighted_choice([("a", 3.0), ("b", 1.0)]) for _ in range(4000)]
    c = Counter(samples)
    # a должно встречаться заметно чаще b
    assert c["a"] > c["b"] * 2
