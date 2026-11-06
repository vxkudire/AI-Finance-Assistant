import pandas as pd

from src.data import market_data


def test_market_overview_returns_actual_levels_and_normalized_comparison(monkeypatch):
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    closes = pd.DataFrame({
        "^GSPC": [6000.0, 6060.0],
        "^DJI": [42000.0, 41580.0],
        "^VIX": [15.0, 18.0],
        "^IXIC": [float("nan"), float("nan")],
    }, index=dates)
    download_args = {}

    def download(symbols, **kwargs):
        download_args["symbols"] = symbols
        download_args.update(kwargs)
        return pd.concat({"Close": closes}, axis=1)

    monkeypatch.setattr(market_data, "get_quotes", lambda symbols: [])
    monkeypatch.setattr(market_data.yf, "download", download)

    result = market_data.get_market_overview("5d")

    assert download_args["period"] == "5d"
    assert "^VIX" in download_args["symbols"]
    assert result["index_levels"]["S&P 500"].tolist() == [6000.0, 6060.0]
    assert result["index_levels"]["VIX"].tolist() == [15.0, 18.0]
    assert list(result["index_levels"].columns) == ["S&P 500", "Dow Jones", "VIX"]
    assert "Nasdaq" not in result["index_levels"].columns
    assert result["history"]["S&P 500"].tolist() == [100.0, 101.0]
    assert "VIX" not in result["history"].columns


def test_market_overview_does_not_fill_missing_actual_levels(monkeypatch):
    closes = pd.DataFrame({"^GSPC": [6000.0, None, 6060.0], "^DJI": [42000.0, 42100.0, 42200.0]})
    monkeypatch.setattr(market_data, "get_quotes", lambda symbols: [])
    monkeypatch.setattr(market_data.yf, "download", lambda *args, **kwargs: pd.concat({"Close": closes}, axis=1))

    result = market_data.get_market_overview()

    assert pd.isna(result["index_levels"]["S&P 500"].iloc[1])
    assert result["history"]["S&P 500"].iloc[1] == 100.0


def test_market_overview_handles_unavailable_history(monkeypatch):
    monkeypatch.setattr(market_data, "get_quotes", lambda symbols: [])
    monkeypatch.setattr(market_data.yf, "download", lambda *args, **kwargs: pd.DataFrame())

    result = market_data.get_market_overview()

    assert result["index_levels"] is None
    assert result["history"] is None

