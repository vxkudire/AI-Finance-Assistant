"""Market data via yfinance (free, can be ~15 min delayed). Swap this module for Polygon/Alpha Vantage/etc. if needed."""
from datetime import datetime, timezone
from typing import Any

import yfinance as yf
import streamlit as st

from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning


@st.cache_data(ttl=60, max_entries=500)
def get_quote(ticker: str, cache_version: str | int = 0) -> dict | None:
    with ignore_yfinance_dataframe_inplace_warning():
        try:
            fi = yf.Ticker(ticker).fast_info
            price, prev = float(fi["last_price"]), float(fi["previous_close"])
        except Exception:
            try:
                closes = yf.Ticker(ticker).history(period="5d")["Close"].dropna()
                if closes.empty:
                    return None
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) > 1 else price
            except Exception:
                return None
    return {"ticker": ticker, "price": price, "prev_close": prev,
            "change_pct": (price / prev - 1) * 100 if prev else 0.0}


def get_quotes(tickers: list[str], cache_version: str | int = 0) -> list[dict[Any, Any] | None]:
    return [q for q in (get_quote(t, cache_version) for t in tickers) if q]


MARKET_INDICES = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq", "^RUT": "Russell 2000", "^VIX": "VIX"}
SECTOR_ETFS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health care", "XLE": "Energy",
    "XLY": "Consumer discretionary", "XLP": "Consumer staples", "XLI": "Industrials",
    "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real estate", "XLC": "Communication",
}


def get_market_overview(period: str = "1mo", cache_version: str | int = 0) -> dict:
    """Index/sector quotes plus index levels and normalized performance for the given period."""
    symbols = list(MARKET_INDICES) + list(SECTOR_ETFS)
    quote_data = get_quotes(symbols, cache_version) if cache_version else get_quotes(symbols)
    quotes = {q["ticker"]: q for q in quote_data}
    history = None
    index_levels = None
    with ignore_yfinance_dataframe_inplace_warning():
        try:
            closes = yf.download(list(MARKET_INDICES), period=period, progress=False, auto_adjust=True)["Close"]
            closes = closes.dropna(how="all").dropna(axis=1, how="all")
            if not closes.empty and len(closes.columns):
                available = [symbol for symbol in MARKET_INDICES if symbol in closes.columns]
                index_levels = closes[available].rename(columns=MARKET_INDICES) if available else None
                comparison = closes.reindex(columns=list(MARKET_INDICES)[:4]).dropna(axis=1, how="all").ffill()
                if not comparison.empty:
                    history = (comparison / comparison.iloc[0] * 100).rename(columns=MARKET_INDICES)
        except Exception:
            history = None
            index_levels = None
    return {
        "indices": [{**quotes[s], "name": n} for s, n in MARKET_INDICES.items() if s in quotes],
        "sectors": [{**quotes[s], "name": n} for s, n in SECTOR_ETFS.items() if s in quotes],
        "history": history,
        "index_levels": index_levels,
        "as_of": datetime.now(timezone.utc),
    }


def format_quotes(quotes: list[dict]) -> str:
    if not quotes:
        return "No quote data could be retrieved. Tell the user live data is unavailable right now."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Quotes as of {now} (Yahoo Finance via yfinance; may be delayed):"]
    lines += [f"- {q['ticker']}: {q['price']:.2f} ({q['change_pct']:+.2f}% vs previous close)" for q in quotes]
    return "\n".join(lines)
