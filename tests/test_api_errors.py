from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from yfinance.exceptions import YFRateLimitError

from src.core import base_agent
from src.data import market_data, news_data, portfolio
from src.utils import api_errors


def http_error(status, headers=None):
    return HTTPError("https://example.test", status, "failure", headers or {}, None)


def test_retry_transient_failure_and_recover(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr(api_errors.time, "sleep", delays.append)
    monkeypatch.setattr(api_errors.random, "uniform", lambda *_: 0.25)

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise http_error(503)
        return "ok"

    assert api_errors.call_with_retry(operation, "test") == "ok"
    assert len(calls) == 3
    assert delays == [0.25, 0.5]


@pytest.mark.parametrize("error", [http_error(401), http_error(429, {"Retry-After": "30"})])
def test_no_retry_for_permanent_error_or_long_retry_after(monkeypatch, error):
    calls = []
    monkeypatch.setattr(api_errors.time, "sleep", lambda _: pytest.fail("unexpected sleep"))

    def operation():
        calls.append(1)
        raise error

    with pytest.raises(HTTPError):
        api_errors.call_with_retry(operation, "test")
    assert len(calls) == 1


def test_retry_after_and_network_failure(monkeypatch):
    delays = []
    failures = iter([http_error(429, {"Retry-After": "1"}), URLError("offline")])
    monkeypatch.setattr(api_errors.time, "sleep", delays.append)
    monkeypatch.setattr(api_errors.random, "uniform", lambda *_: 0.25)

    def operation():
        error = next(failures, None)
        if error:
            raise error
        return True

    assert api_errors.call_with_retry(operation, "test")
    assert delays == [1, 0.5]


def test_quote_failure_not_cached_and_rate_limit_stops_batch(monkeypatch):
    market_data.get_quote.clear()
    calls = []
    monkeypatch.setattr(api_errors.time, "sleep", lambda _: None)

    class Ticker:
        @property
        def fast_info(self):
            calls.append(1)
            if len(calls) <= 3:
                raise YFRateLimitError()
            return {"last_price": 101, "previous_close": 100}

    monkeypatch.setattr(market_data.yf, "Ticker", lambda _: Ticker())
    try:
        assert market_data.get_quotes(["A", "B"]) == []
        assert len(calls) == 3
        assert market_data.get_quotes(["A"])[0]["price"] == 101
        assert len(calls) == 4
    finally:
        market_data.get_quote.clear()


def test_market_overview_skips_history_after_rate_limit(monkeypatch):
    monkeypatch.setattr(market_data, "get_quotes_with_status", lambda *_: ([], True))
    monkeypatch.setattr(market_data, "_market_history", lambda *_: pytest.fail("unexpected history request"))
    result = market_data.get_market_overview()
    assert result["index_levels"] is None
    assert len(result["missing_quotes"]) == len(market_data.MARKET_INDICES) + len(market_data.SECTOR_ETFS)


def test_market_history_failure_not_cached(monkeypatch):
    market_data._market_history.clear()
    calls = []

    def download(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise http_error(403)
        import pandas as pd
        return pd.concat({"Close": pd.DataFrame({"^GSPC": [10.0, 11.0]})}, axis=1)

    monkeypatch.setattr(market_data.yf, "download", download)
    try:
        with pytest.raises(HTTPError):
            market_data._market_history("1mo", 0)
        history, levels = market_data._market_history("1mo", 0)
        assert history["S&P 500"].iloc[1] == pytest.approx(110)
        assert levels["S&P 500"].iloc[1] == 11
        assert len(calls) == 2
    finally:
        market_data._market_history.clear()


def test_portfolio_retains_partial_results_and_stops_after_rate_limit(monkeypatch):
    calls = []

    def quote(ticker, version):
        calls.append(ticker)
        if ticker == "B":
            raise api_errors.ServiceUnavailable("Yahoo Finance", rate_limited=True)
        return {"price": 10}

    monkeypatch.setattr(portfolio, "get_quote", quote)
    result = portfolio.analyze_portfolio([
        {"ticker": "A", "shares": 1}, {"ticker": "B", "shares": 1}, {"ticker": "C", "shares": 2},
    ], include_sector=False)
    assert [row["ticker"] for row in result["rows"]] == ["A"]
    assert result["skipped"] == ["B", "C"]
    assert calls == ["A", "B"]
    assert "Partial value (priced holdings only)" in portfolio.format_portfolio_report(result)


def test_sector_failure_not_cached_and_recovery(monkeypatch):
    portfolio._sector.clear()
    calls = []

    class Ticker:
        @property
        def info(self):
            calls.append(1)
            if len(calls) == 1:
                raise http_error(403)
            return {"sector": "Technology"}

    monkeypatch.setattr(portfolio.yf, "Ticker", lambda _: Ticker())
    try:
        with pytest.raises(api_errors.ServiceUnavailable):
            portfolio._sector("A")
        assert portfolio._sector("A") == "Technology"
        assert len(calls) == 2
    finally:
        portfolio._sector.clear()


def test_failed_news_is_not_cached_and_partial_failure_reported(monkeypatch):
    news_data._fetch_feed.clear()
    calls = []

    def open_feed(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise http_error(403)
        return BytesIO(b'<rss version="2.0"><channel><title>News</title><item><title>Headline</title></item></channel></rss>')

    monkeypatch.setattr(news_data, "urlopen", open_feed)
    try:
        items, failed = news_data.fetch_news_with_status(["https://example.test/rss"])
        assert items == [] and failed
        items, failed = news_data.fetch_news_with_status(["https://example.test/rss"])
        assert not failed and items[0]["title"] == "Headline"
        assert len(calls) == 2
    finally:
        news_data._fetch_feed.clear()


def test_news_preserves_other_sources_after_one_fails(monkeypatch):
    def fetch(url):
        if url == "bad":
            raise http_error(503)
        return [{"source": "Good", "title": "Headline", "summary": "", "published": "", "link": ""}]

    monkeypatch.setattr(news_data, "_fetch_feed", fetch)
    items, failed = news_data.fetch_news_with_status(["bad", "good"])
    assert failed
    assert items[0]["title"] == "Headline"


def test_safe_user_messages_do_not_include_provider_error():
    error = http_error(429)
    assert "too many requests" in api_errors.user_error_message(error)
    assert "example.test" not in api_errors.user_error_message(error)


def test_agent_discloses_knowledge_base_failure(monkeypatch):
    class Model:
        def invoke(self, messages):
            assert "knowledge base is unavailable" in messages[0].content
            return AIMessage(content="A general answer.")

    def fail_retrieval(*args):
        raise http_error(503)

    monkeypatch.setattr(base_agent, "retrieve", fail_retrieval)
    agent = object.__new__(base_agent.BaseAgent)
    agent.llm = Model()
    agent.namespaces = ["finance_qa"]
    agent.log = api_errors.log
    result = agent.run({"messages": [HumanMessage(content="What is a bond?")]})
    assert "knowledge base was unavailable" in result["messages"][0].content
    assert result["sources"] == []
