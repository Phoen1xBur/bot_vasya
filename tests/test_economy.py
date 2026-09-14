"""Тесты балансировки экономики: работа vs кража (чистая логика)."""
from shared.economy import (
    ROB_PENALTY,
    ROB_POLICE_CHANCE,
    ROB_SUCCESS_CHANCE,
    ROB_MAX,
    ROB_MIN,
    WORK_MAX,
    WORK_MIN,
    apply_work_bonus,
    balance_report,
    expected_rob_value,
    expected_work_value,
    roll_rob_outcome,
    roll_work_income,
)
from shared.enums import RandomRob, SubscriptionTier


def test_roll_work_income_range():
    for _ in range(200):
        v = roll_work_income()
        assert WORK_MIN <= v <= WORK_MAX


def test_apply_work_bonus_free():
    income, bonus = apply_work_bonus(100, SubscriptionTier.FREE)
    assert income == 100
    assert bonus == 0.0


def test_apply_work_bonus_vip():
    income, bonus = apply_work_bonus(100, SubscriptionTier.VIP)
    assert income == 110
    assert bonus == 0.10


def test_apply_work_bonus_premium():
    income, bonus = apply_work_bonus(100, SubscriptionTier.PREMIUM)
    assert income == 125
    assert bonus == 0.25


def test_apply_work_bonus_elite():
    income, bonus = apply_work_bonus(100, SubscriptionTier.ELITE)
    assert income == 150
    assert bonus == 0.50


def test_expected_values():
    # работа: среднее (50+150)/2 = 100
    assert expected_work_value() == 100
    # кража: 0.4 * 300 - 0.3 * 100 = 120 - 30 = 90
    assert expected_rob_value() == 90


def test_rob_not_massively_more_profitable_than_work():
    # Кража не должна быть кратно выгоднее работы (иначе баланс сломан)
    assert expected_rob_value() < expected_work_value() * 2


def test_roll_rob_outcome_valid_values():
    seen = {roll_rob_outcome() for _ in range(1000)}
    assert seen <= {RandomRob.SUCCESS, RandomRob.FAIL, RandomRob.POLICE}
    # за 1000 бросков успех точно выпадет
    assert RandomRob.SUCCESS in seen


def test_balance_report_shape():
    rep = balance_report()
    assert rep["work_range"] == [WORK_MIN, WORK_MAX]
    assert rep["rob_range"] == [ROB_MIN, ROB_MAX]
    assert rep["rob_chances"]["success"] == ROB_SUCCESS_CHANCE
    assert rep["rob_chances"]["police"] == ROB_POLICE_CHANCE
    assert rep["rob_chances"]["police"] == ROB_POLICE_CHANCE
    assert ROB_PENALTY == 100
