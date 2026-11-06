import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest

pytest.importorskip("mcp")
from src import mcp_server


def test_registered_tools():
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert names == {"get_quotes", "get_market_overview", "get_financial_news", "analyze_portfolio",
                     "project_future_value", "required_monthly_contribution"}


def test_get_quotes_normalizes_dedupes_and_reports_missing(monkeypatch):
    seen = []

    def fake(symbols):
        seen.extend(symbols)
        return [{"ticker": "AAPL", "price": 1.0, "prev_close": 1.0, "change_pct": 0.0}], False

    monkeypatch.setattr(mcp_server, "get_quotes_with_status", fake)
    result = mcp_server.get_quotes([" aapl", "AAPL", "^gspc"])
    assert seen == ["AAPL", "^GSPC"]
    assert result["missing"] == ["^GSPC"] and result["rate_limited"] is False


@pytest.mark.parametrize("tickers", [[], ["bad ticker"], ["A"] * 26, [""], ["../x"]])
def test_get_quotes_rejects_bad_input(tickers):
    with pytest.raises(ValueError):
        mcp_server.get_quotes(tickers)


def test_market_overview_serializes_frames(monkeypatch):
    frame = pd.DataFrame({"S&P 500": [100.0, 101.5]}, index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
    monkeypatch.setattr(mcp_server, "_market_overview", lambda period: {
        "indices": [], "sectors": [], "history": frame, "index_levels": None,
        "as_of": datetime(2024, 1, 3, tzinfo=timezone.utc), "missing_quotes": ["XLK"]})
    result = mcp_server.get_market_overview("5d")
    assert result["normalized_performance"][1]["S&P 500"] == 101.5
    assert result["index_levels"] == [] and result["missing_quotes"] == ["XLK"]


def test_news_uses_config_feeds_and_validates_limit(monkeypatch):
    monkeypatch.setattr(mcp_server, "load_config", lambda: {"data": {"news_feeds": ["u"], "max_news_items": 3}})
    calls = []
    monkeypatch.setattr(mcp_server, "fetch_news_with_status",
                        lambda feeds, terms, limit: (calls.append((feeds, terms, limit)) or [], True))
    assert mcp_server.get_financial_news([" rates ", ""])["some_feeds_failed"] is True
    assert calls == [(["u"], ["rates"], 3)]
    for bad in (0, 26, True):
        with pytest.raises(ValueError):
            mcp_server.get_financial_news(limit=bad)


def test_analyze_portfolio_validates_and_delegates(monkeypatch):
    got = {}
    monkeypatch.setattr(mcp_server, "_analyze_portfolio",
                        lambda holdings, include_sector: got.update(h=holdings, s=include_sector) or {"rows": []})
    mcp_server.analyze_portfolio([{"ticker": "msft", "shares": 2, "cost_basis": 10}], include_sector=False)
    assert got == {"h": [{"ticker": "MSFT", "shares": 2.0, "cost_basis": 10.0}], "s": False}
    for bad in ([], ["x"], [{"ticker": "MSFT", "shares": 0}], [{"ticker": "MSFT", "shares": "2"}],
                [{"ticker": "MSFT", "shares": 1, "cost_basis": float("nan")}], [{"ticker": "", "shares": 1}]):
        with pytest.raises(ValueError):
            mcp_server.analyze_portfolio(bad)


def test_calculators_match_utils_and_validate():
    assert mcp_server.project_future_value(1000, 100, 0, 1)["future_value"] == 2200
    assert mcp_server.required_monthly_contribution(1200, 0, 0, 1)["required_monthly_contribution"] == 100
    for call in (lambda: mcp_server.project_future_value(-1, 0, 0.05, 1),
                 lambda: mcp_server.project_future_value(1, 0, float("inf"), 1),
                 lambda: mcp_server.required_monthly_contribution(1, 0, 0.05, 101)):
        with pytest.raises(ValueError):
            call()
