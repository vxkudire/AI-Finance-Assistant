from types import SimpleNamespace

import pandas as pd
import pytest
from langchain_core.messages import HumanMessage

from src.data import market_data, portfolio
from src.utils import api_errors, helpers


def test_message_helpers_handle_content_blocks_and_missing_human():
    message = HumanMessage(content=[{"type": "text", "text": "first"}, "tail"])
    assert helpers.message_text(message) == "first tail"
    assert helpers.last_user_text([SimpleNamespace(type="ai", content="answer")]) == ""
    assert helpers.last_user_text([message]) == "first tail"


def test_ticker_and_topic_helpers_apply_stop_words_limits_and_deduplication():
    assert helpers.extract_tickers("AAPL vs AAPL, ETF and $nvda", limit=1) == ["AAPL"]
    assert helpers.extract_tickers("ROTH ETF GDP") == []
    assert helpers.topic_terms("Latest news about Nvidia and AAPL markets") == ["AAPL", "nvidia"]


def test_api_error_classification_and_retry_after_headers(monkeypatch):
    response_error = SimpleNamespace(response=SimpleNamespace(status_code=503, headers={"Retry-After": "1.5"}))
    assert api_errors.http_status(response_error) == 503
    assert api_errors.is_transient(response_error)
    assert api_errors._retry_after(response_error) == 1.5
    assert api_errors.http_status(SimpleNamespace(code=401)) == 401
    assert not api_errors.is_transient(SimpleNamespace(status_code=404))
    assert api_errors.user_error_message(SimpleNamespace(status_code=403)).startswith("A service could not be accessed")

    delays = []
    monkeypatch.setattr(api_errors.time, "sleep", delays.append)
    monkeypatch.setattr(api_errors.random, "uniform", lambda *_: 0.1)
    attempts = []

    class TemporaryError(Exception):
        status_code = 503
        headers = {"Retry-After": "invalid"}

    def operation():
        attempts.append(None)
        if len(attempts) < 2:
            raise TemporaryError()
        return "recovered"

    assert api_errors.call_with_retry(operation, "test") == "recovered"
    assert delays == [0.1]


def test_quote_uses_history_fallback_after_unusable_fast_info(monkeypatch):
    market_data.get_quote.clear()

    class Ticker:
        @property
        def fast_info(self):
            raise KeyError("fast quote unavailable")

        def history(self, period):
            assert period == "5d"
            return pd.DataFrame({"Close": [9.0, 10.0]})

    monkeypatch.setattr(market_data.yf, "Ticker", lambda symbol: Ticker())
    try:
        quote = market_data.get_quote("TEST_FALLBACK")
        assert quote == {"ticker": "TEST_FALLBACK", "price": 10.0, "prev_close": 9.0,
                         "change_pct": pytest.approx((10 / 9 - 1) * 100)}
    finally:
        market_data.get_quote.clear()


def test_quote_validation_and_batch_status(monkeypatch):
    market_data.get_quote.clear()
    calls = []

    def quote(ticker, version):
        calls.append(ticker)
        if ticker == "BAD":
            raise api_errors.ServiceUnavailable("Yahoo Finance")
        if ticker == "LIMIT":
            raise api_errors.ServiceUnavailable("Yahoo Finance", rate_limited=True)
        return {"ticker": ticker}

    monkeypatch.setattr(market_data, "get_quote", quote)
    assert market_data.get_quotes_with_status(["A", "BAD", "B"]) == (
        [{"ticker": "A"}, {"ticker": "B"}], False
    )
    assert market_data.get_quotes_with_status(["A", "LIMIT", "B"]) == ([{"ticker": "A"}], True)
    assert calls[-2:] == ["A", "LIMIT"]
    assert "No quote data" in market_data.format_quotes([])


def test_portfolio_metrics_and_unavailable_holdings(monkeypatch):
    prices = {"AAA": 100.0, "BBB": 50.0}
    monkeypatch.setattr(portfolio, "get_quote", lambda ticker, version: (
        {"price": prices[ticker]} if ticker in prices else None
    ))
    monkeypatch.setattr(portfolio, "_sector", lambda ticker, version: "Technology")

    result = portfolio.analyze_portfolio([
        {"ticker": "AAA", "shares": 2, "cost_basis": 80},
        {"ticker": "BBB", "shares": 2},
        {"ticker": "MISSING", "shares": 1},
        {"ticker": "", "shares": 1},
        {"ticker": "BAD", "shares": 0},
    ])

    assert result["total_value"] == 300
    assert result["top_weight"] == pytest.approx(2 / 3)
    assert result["hhi"] == pytest.approx((2 / 3) ** 2 + (1 / 3) ** 2)
    assert result["effective_holdings"] == pytest.approx(1.8)
    assert result["sectors"] == {"Technology": 1}
    assert result["skipped"] == ["MISSING"]
    assert result["rows"][0]["gain_pct"] == pytest.approx(25)
    report = portfolio.format_portfolio_report(result)
    assert "Partial value (priced holdings only)" in report
    assert "Could not price: MISSING" in report

    empty = portfolio.analyze_portfolio([{"ticker": "MISSING", "shares": 1}])
    assert "No holdings could be priced" in portfolio.format_portfolio_report(empty)


def test_portfolio_sector_failure_uses_unknown_and_rate_limit_skips_rest(monkeypatch):
    monkeypatch.setattr(portfolio, "get_quote", lambda ticker, version: {"price": 10.0})
    monkeypatch.setattr(portfolio, "_sector", lambda ticker, version: (_ for _ in ()).throw(
        api_errors.ServiceUnavailable("Yahoo Finance", rate_limited=True)
    ))

    result = portfolio.analyze_portfolio([
        {"ticker": "AAA", "shares": 1}, {"ticker": "BBB", "shares": 1},
    ])

    assert result["rows"][0]["sector"] == "Unknown"
    assert result["skipped"] == ["BBB"]
    assert "Unknown" in portfolio.format_portfolio_report(result)
