"""Market data via yfinance (free, can be ~15 min delayed). Swap this module for Polygon/Alpha Vantage/etc. if needed."""
from datetime import datetime, timezone
import math
import yfinance as yf
import streamlit as st

from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning
from src.utils.api_errors import ServiceUnavailable, call_with_retry, http_status, is_rate_limit, is_transient
from src.utils.logger import get_logger

log = get_logger("market_data")


@st.cache_data(ttl=60, max_entries=500)
def get_quote(ticker: str, cache_version: str | int = 0) -> dict:
    with ignore_yfinance_dataframe_inplace_warning():
        try:
            def fast_quote():
                fi = yf.Ticker(ticker).fast_info
                price, prev = float(fi["last_price"]), float(fi["previous_close"])
                if not math.isfinite(price) or price <= 0 or not math.isfinite(prev) or prev <= 0:
                    raise ValueError("Invalid quote")
                return price, prev

            price, prev = call_with_retry(fast_quote, "Yahoo Finance")
        except Exception as exc:
            status = http_status(exc)
            if is_transient(exc) or (isinstance(status, int) and 400 <= status < 500):
                raise ServiceUnavailable("Yahoo Finance", rate_limited=is_rate_limit(exc)) from exc
            log.warning("Fast quote unavailable for %s (%s); trying price history", ticker, type(exc).__name__)
            try:
                closes = call_with_retry(
                    lambda: yf.Ticker(ticker).history(period="5d")["Close"].dropna(), "Yahoo Finance"
                )
                if closes.empty:
                    raise ServiceUnavailable("Yahoo Finance")
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) > 1 else price
                if not math.isfinite(price) or price <= 0 or not math.isfinite(prev) or prev <= 0:
                    raise ValueError("Invalid quote")
            except Exception as fallback_exc:
                raise ServiceUnavailable("Yahoo Finance", rate_limited=is_rate_limit(fallback_exc)) from fallback_exc
    return {"ticker": ticker, "price": price, "prev_close": prev,
            "change_pct": (price / prev - 1) * 100 if prev else 0.0}


def get_quotes_with_status(tickers: list[str], cache_version: str | int = 0) -> tuple[list[dict], bool]:
    quotes = []
    for ticker in tickers:
        try:
            quote = get_quote(ticker, cache_version)
            if quote:
                quotes.append(quote)
        except ServiceUnavailable as exc:
            log.warning("Quote unavailable for %s (%s)", ticker, "rate limited" if exc.rate_limited else "provider failure")
            if exc.rate_limited:
                return quotes, True
    return quotes, False


def get_quotes(tickers: list[str], cache_version: str | int = 0) -> list[dict]:
    return get_quotes_with_status(tickers, cache_version)[0]


MARKET_INDICES = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq", "^RUT": "Russell 2000", "^VIX": "VIX"}
SECTOR_ETFS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health care", "XLE": "Energy",
    "XLY": "Consumer discretionary", "XLP": "Consumer staples", "XLI": "Industrials",
    "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real estate", "XLC": "Communication",
}


@st.cache_data(ttl=60, max_entries=32)
def _market_history(period: str, cache_version: str | int):
    with ignore_yfinance_dataframe_inplace_warning():
        closes = call_with_retry(
            lambda: yf.download(list(MARKET_INDICES), period=period, progress=False, auto_adjust=True)["Close"],
            "Yahoo Finance",
        )
    closes = closes.dropna(how="all").dropna(axis=1, how="all")
    if closes.empty or not len(closes.columns):
        raise ServiceUnavailable("Yahoo Finance")
    available = [symbol for symbol in MARKET_INDICES if symbol in closes.columns]
    index_levels = closes[available].rename(columns=MARKET_INDICES) if available else None
    comparison = closes.reindex(columns=list(MARKET_INDICES)[:4]).dropna(axis=1, how="all").ffill()
    history = (comparison / comparison.iloc[0] * 100).rename(columns=MARKET_INDICES) if not comparison.empty else None
    return history, index_levels


def get_market_overview(period: str = "1mo", cache_version: str | int = 0) -> dict:
    """Index/sector quotes plus index levels and normalized performance for the given period."""
    symbols = list(MARKET_INDICES) + list(SECTOR_ETFS)
    quote_data, rate_limited = get_quotes_with_status(symbols, cache_version)
    quotes = {q["ticker"]: q for q in quote_data}
    history = None
    index_levels = None
    if not rate_limited:
        try:
            history, index_levels = _market_history(period, cache_version)
        except Exception as exc:
            log.warning("Market history unavailable (%s)", type(exc).__name__)
    return {
        "indices": [{**quotes[s], "name": n} for s, n in MARKET_INDICES.items() if s in quotes],
        "sectors": [{**quotes[s], "name": n} for s, n in SECTOR_ETFS.items() if s in quotes],
        "history": history,
        "index_levels": index_levels,
        "as_of": datetime.now(timezone.utc),
        "missing_quotes": [symbol for symbol in symbols if symbol not in quotes],
    }


def format_quotes(quotes: list[dict]) -> str:
    if not quotes:
        return "No quote data could be retrieved. Tell the user live data is unavailable right now."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Quotes as of {now} (Yahoo Finance via yfinance; may be delayed):"]
    lines += [f"- {q['ticker']}: {q['price']:.2f} ({q['change_pct']:+.2f}% vs previous close)" for q in quotes]
    return "\n".join(lines)
