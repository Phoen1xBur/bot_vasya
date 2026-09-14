"""Балансировка экономики: работа vs кража.

Цель:
- работа — стабильный доход, низкий риск.
- кража — высокий риск / высокий доход, но с шансом провала, штрафа и тюрьмы.
- Ожидаемый доход от кражи ≈ работе, но с большой дисперсией.
- Множители подписок — только к работе (стимул + балансировка).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from shared.config import get_settings
from shared.enums import RandomRob, SubscriptionTier
from shared.models.subscription import TIER_WORK_BONUS
from shared.utils import weighted_choice

_settings = get_settings()

# Кулдауны
WORK_COOLDOWN = timedelta(minutes=_settings.WORK_COOLDOWN_MINUTES)  # 1 час
ROB_COOLDOWN = timedelta(minutes=_settings.ROB_COOLDOWN_MINUTES)  # 6 часов
PRISON_TIME = timedelta(hours=_settings.PRISON_HOURS)  # 2 часа

# Диапазоны заработка
WORK_MIN = 50
WORK_MAX = 150

ROB_MIN = 100
ROB_MAX = 500

# Шансы кражи
ROB_SUCCESS_CHANCE = 40.0   # успех
ROB_FAIL_CHANCE = 30.0      # провал без тюрьмы
ROB_POLICE_CHANCE = 30.0    # поймали → тюрьма + штраф

ROB_PENALTY = 100  # штраф при поимке

# Минимальный баланс жертвы для кражи
ROB_VICTIM_MIN_MONEY = 10


@dataclass
class WorkResult:
    income: int
    profession_name: str
    accompanying_text: str | None
    bonus: float  # множитель подписки (0.0 — нет)


@dataclass
class RobResult:
    outcome: RandomRob
    amount: int  # украденная сумма (0 при провале)
    penalty: int = 0  # штраф при поимке


def roll_work_income() -> int:
    """Базовый заработок с работы (без бонуса подписки)."""
    return random.randint(WORK_MIN, WORK_MAX)


def apply_work_bonus(base_income: int, tier: SubscriptionTier) -> tuple[int, float]:
    """Применить множитель подписки к доходу работы."""
    bonus = TIER_WORK_BONUS.get(tier, 0.0)
    if bonus <= 0:
        return base_income, 0.0
    return int(round(base_income * (1 + bonus))), bonus


def roll_rob_outcome() -> RandomRob:
    """Определить исход кражи."""
    return weighted_choice(
        [
            (RandomRob.SUCCESS, ROB_SUCCESS_CHANCE),
            (RandomRob.FAIL, ROB_FAIL_CHANCE),
            (RandomRob.POLICE, ROB_POLICE_CHANCE),
        ]
    )


def roll_rob_amount() -> int:
    """Сумма кражи (до применения исхода)."""
    return random.randint(ROB_MIN, ROB_MAX)


def expected_rob_value() -> float:
    """Ожидаемый доход от кражи для контроля баланса.

    = P(успех)*E[сумма] - P(полиция)*штраф
    """
    avg_amount = (ROB_MIN + ROB_MAX) / 2
    p_success = ROB_SUCCESS_CHANCE / 100
    p_police = ROB_POLICE_CHANCE / 100
    return p_success * avg_amount - p_police * ROB_PENALTY


def expected_work_value() -> float:
    """Ожидаемый доход от работы."""
    return (WORK_MIN + WORK_MAX) / 2


def balance_report() -> dict:
    """Отчёт о балансе экономики (для админки/логов)."""
    return {
        "work_expected": expected_work_value(),
        "rob_expected": expected_rob_value(),
        "work_range": [WORK_MIN, WORK_MAX],
        "rob_range": [ROB_MIN, ROB_MAX],
        "rob_chances": {
            "success": ROB_SUCCESS_CHANCE,
            "fail": ROB_FAIL_CHANCE,
            "police": ROB_POLICE_CHANCE,
        },
        "work_cooldown_min": _settings.WORK_COOLDOWN_MINUTES,
        "rob_cooldown_min": _settings.ROB_COOLDOWN_MINUTES,
        "prison_hours": _settings.PRISON_HOURS,
    }
