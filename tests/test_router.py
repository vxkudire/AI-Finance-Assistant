import pytest

from src.workflow.router import keyword_fallback


@pytest.mark.parametrize("text,expected", [
    ("What are the tax implications of a Roth conversion?", "tax_agent"),
    ("Analyze my portfolio", "portfolio_agent"),
    ("I want to retire in 20 years, how much should I save?", "goal_planning_agent"),
    ("Summarize the latest news on interest rates", "news_agent"),
    ("What is the price of AAPL today?", "market_agent"),
    ("What is an ETF?", "finance_qa_agent"),
])
def test_keyword_fallback(text, expected):
    assert keyword_fallback(text) == expected
