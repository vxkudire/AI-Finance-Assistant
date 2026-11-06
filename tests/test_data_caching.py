from types import SimpleNamespace

from src.data import market_data


def test_quote_cache_reuses_results_and_refresh_version_bypasses_cache(monkeypatch):
    calls = []

    class FakeTicker:
        @property
        def fast_info(self):
            calls.append("quote")
            return {"last_price": 101.0, "previous_close": 100.0}

    market_data.get_quote.clear()
    monkeypatch.setattr(market_data.yf, "Ticker", lambda ticker: FakeTicker())

    try:
        first = market_data.get_quote("TEST")
        repeated = market_data.get_quote("TEST")
        refreshed = market_data.get_quote("TEST", cache_version=1)

        assert first == repeated
        assert refreshed == first
        assert calls == ["quote", "quote"]
    finally:
        market_data.get_quote.clear()
