"""Deterministic finance maths - never let the LLM do arithmetic."""


def future_value(present: float, monthly: float, annual_rate: float, years: float) -> float:
    r, n = annual_rate / 12, int(round(years * 12))
    if r == 0:
        return present + monthly * n
    return present * (1 + r) ** n + monthly * (((1 + r) ** n - 1) / r)


def required_monthly_contribution(target: float, present: float, annual_rate: float, years: float) -> float:
    r, n = annual_rate / 12, int(round(years * 12))
    if n <= 0:
        return max(target - present, 0.0)
    gap = target - present * (1 + r) ** n
    if gap <= 0:
        return 0.0
    return gap / n if r == 0 else gap * r / ((1 + r) ** n - 1)
