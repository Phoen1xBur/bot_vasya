"""Тесты таргетинга рекламы по уникальным пользователям (у.п.).

Ключевой сценарий: подобрать подмножество чатов с суммарным у.п.
(с учётом пересечений!) ≈ запросу.
"""
import shared.ad_targeting as at
from shared.ad_targeting import _greedy_select, count_total_unique_users, select_chats_for_target


# ----------------- Чистый жадный алгоритм -----------------


def test_greedy_select_basic():
    chats = [(1, {1, 2, 3}), (2, {3, 4, 5}), (3, {6, 7, 8})]
    selected, covered = _greedy_select(chats, 6, 0.01)
    assert len(covered) >= 5  # >= 99% от 6
    assert len(covered) <= 6  # не превышает 101%
    assert 1 in selected


def test_greedy_select_intersections_overshoot():
    """Один большой чат превышает цель — greedy берёт его, выходит за допуск."""
    chats = [(1, set(range(1, 11))), (2, set(range(1, 6))), (3, {6, 7, 8})]
    selected, covered = _greedy_select(chats, 8, 0.01)
    assert 1 in selected
    assert len(covered) == 10  # весь чат 1


def test_greedy_select_empty():
    selected, covered = _greedy_select([], 100)
    assert selected == []
    assert covered == set()


# ----------------- Интеграция: пересечения считаются один раз -----------------


async def test_select_chats_intersections_counted_once(monkeypatch):
    """Чаты с пересечениями: 4 и 5 в обоих — считаются 1 раз.

    Чат 100: {1,2,3,4,5}; чат 200: {4,5,6,7,8}. union = {1..8} = 8 у.п.
    """
    async def fake_load():
        return [(100, {1, 2, 3, 4, 5}), (200, {4, 5, 6, 7, 8})]

    monkeypatch.setattr(at, "_load_chat_sets", fake_load)
    res = await select_chats_for_target(8, 0.01)
    assert res.target == 8
    assert res.total_unique_users == 8  # не 10 — пересечения учтены
    assert set(res.selected_chats) == {100, 200}
    assert res.within_tolerance is True


async def test_select_chats_empty_db(monkeypatch):
    async def fake_load():
        return []

    monkeypatch.setattr(at, "_load_chat_sets", fake_load)
    res = await select_chats_for_target(5000, 0.01)
    assert res.selected_chats == []
    assert res.total_unique_users == 0
    assert res.within_tolerance is False


async def test_count_total_unique_users(monkeypatch):
    async def fake_load():
        return [(1, {1, 2}), (2, {2, 3}), (3, {3, 4})]

    monkeypatch.setattr(at, "_load_chat_sets", fake_load)
    # union {1,2,3,4} = 4
    assert await count_total_unique_users() == 4
