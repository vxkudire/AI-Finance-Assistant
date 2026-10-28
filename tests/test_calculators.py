import pytest

from src.utils.calculators import future_value, required_monthly_contribution


def test_zero_rate():
    assert future_value(1000, 100, 0, 1) == 2200
    assert required_monthly_contribution(12000, 0, 0, 1) == pytest.approx(1000)


def test_required_contribution_reaches_target():
    need = required_monthly_contribution(100_000, 5_000, 0.06, 10)
    assert future_value(5_000, need, 0.06, 10) == pytest.approx(100_000, rel=1e-6)


def test_already_funded():
    assert required_monthly_contribution(1000, 5000, 0.05, 5) == 0.0
