"""Алгоритм таргетинга рекламы по уникальным пользователям (у.п.).

Ключевая фича: подобрать подмножество чатов с суммарным у.п.
(с учётом пересечений!) ≈ запросу. Погрешность ±1%.

Подход: жадный алгоритм с учётом пересечений + откат при переборе.
"""

import logging
from dataclasses import dataclass

from shared.models.ad_campaign import ChatUniqueUsersOrm

logger = logging.getLogger(__name__)


@dataclass
class TargetingResult:
    selected_chats: list[int]
    total_unique_users: int
    target: int
    within_tolerance: bool


async def _load_chat_sets() -> list[tuple[int, set[int]]]:
    """Загрузить множества user_id по всем чатам из БД."""
    rows = await ChatUniqueUsersOrm.get_all()
    result = []
    for row in rows:
        if not row.unique_user_ids:
            continue
        result.append((row.chat_id, set(row.unique_user_ids)))
    # Сортируем по размеру множества убывание
    result.sort(key=lambda x: len(x[1]), reverse=True)
    return result


def _greedy_select(
    chat_sets: list[tuple[int, set[int]]],
    target: int,
    tolerance: float = 0.01,
) -> tuple[list[int], set[int]]:
    """Жадно добавляем чаты, пока суммарное у.п. не достигнем цели.

    Учитываем пересечения: union множеств.
    При переборе — откат и пробуем другой чат.
    """
    selected: list[int] = []
    covered: set[int] = set()
    remaining = list(chat_sets)

    lo = int(target * (1 - tolerance))
    hi = int(target * (1 + tolerance))

    while remaining and len(covered) < hi:
        # Выбираем чат, дающий максимум новых уникальных
        best_idx = -1
        best_gain = 0
        for i, (chat_id, users) in enumerate(remaining):
            gain = len(users - covered)
            if gain > best_gain:
                best_gain = gain
                best_idx = i
        if best_idx == -1 or best_gain == 0:
            break
        chat_id, users = remaining.pop(best_idx)
        covered |= users
        selected.append(chat_id)
        if lo <= len(covered) <= hi:
            break

    return selected, covered


async def select_chats_for_target(target_unique_users: int, tolerance: float = 0.01) -> TargetingResult:
    """Подобрать чаты под запрошенное количество у.п.

    :param target_unique_users: запрошенное количество у.п.
    :param tolerance: допустимая погрешность (0.01 = ±1%)
    :return: TargetingResult
    """
    chat_sets = await _load_chat_sets()

    if not chat_sets:
        return TargetingResult(
            selected_chats=[],
            total_unique_users=0,
            target=target_unique_users,
            within_tolerance=False,
        )

    selected, covered = _greedy_select(chat_sets, target_unique_users, tolerance)
    within = abs(len(covered) - target_unique_users) <= target_unique_users * tolerance

    logger.info(
        "Таргетинг: цель=%d, выбрано чатов=%d, у.п.=%d, в допуске=%s",
        target_unique_users,
        len(selected),
        len(covered),
        within,
    )
    return TargetingResult(
        selected_chats=selected,
        total_unique_users=len(covered),
        target=target_unique_users,
        within_tolerance=within,
    )


async def count_total_unique_users() -> int:
    """Общее количество уникальных пользователей во всех чатах (без дублей)."""
    chat_sets = await _load_chat_sets()
    all_users: set[int] = set()
    for _, users in chat_sets:
        all_users |= users
    return len(all_users)
