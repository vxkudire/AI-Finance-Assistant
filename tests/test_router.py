import pytest

from src.workflow.router import keyword_fallback


@pytest.mark.parametrize("text,expected", [
    ("What are the tax implications of a Roth conversion?", "tax"),
    ("Analyze my portfolio", "portfolio"),
    ("I want to retire in 20 years, how much should I save?", "goal_planning"),
    ("Summarize the latest news on interest rates", "news"),
    ("What is the price of AAPL today?", "market"),
    ("What is an ETF?", "finance_qa"),
])
def test_keyword_fallback(text, expected):
    assert keyword_fallback(text) == expected
