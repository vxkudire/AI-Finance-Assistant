"""Market data via yfinance (free, can be ~15 min delayed). Swap this module for Polygon/Alpha Vantage/etc. if needed."""
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning


def get_quote(ticker: str) -> dict | None:
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


def get_quotes(tickers: list[str]) -> list[dict[Any, Any] | None]:
    return [q for q in (get_quote(t) for t in tickers) if q]


def format_quotes(quotes: list[dict]) -> str:
    if not quotes:
        return "No quote data could be retrieved. Tell the user live data is unavailable right now."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Quotes as of {now} (Yahoo Finance via yfinance; may be delayed):"]
    lines += [f"- {q['ticker']}: {q['price']:.2f} ({q['change_pct']:+.2f}% vs previous close)" for q in quotes]
    return "\n".join(lines)
