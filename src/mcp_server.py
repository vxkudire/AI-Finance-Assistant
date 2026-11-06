"""Read-only MCP server (stdio) exposing the app's market, news, portfolio and calculator functions.

Run with: python -m src.mcp_server
"""
import math
import re
from typing import Literal

from mcp.server.fastmcp import FastMCP

from src.core.config import load_config
from src.data.market_data import get_market_overview as _market_overview
from src.data.market_data import get_quotes_with_status
from src.data.news_data import fetch_news_with_status
from src.data.portfolio import analyze_portfolio as _analyze_portfolio
from src.utils import calculators

MAX_TICKERS = 25
MAX_HOLDINGS = 50
MAX_NEWS = 25
MAX_YEARS = 100
_TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,14}$")
Period = Literal["5d", "1mo", "3mo", "6mo", "1y", "ytd"]

mcp = FastMCP("ai-finance-assistant")


def _ticker(value) -> str:
    ticker = str(value or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"Invalid ticker symbol: {value!r}")
    return ticker


def _finite(value, name: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum:g}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum:g}")
    return float(value)


def _frame_records(frame) -> list[dict]:
    if frame is None or frame.empty:
        return []
    out = frame.round(4).reset_index()
    out.iloc[:, 0] = out.iloc[:, 0].astype(str)
    return out.astype(object).where(out.notna(), None).to_dict("records")


@mcp.tool()
def get_quotes(tickers: list[str]) -> dict:
    """Latest quotes (price, previous close, % change) from Yahoo Finance; may be delayed ~15 min.

    Tickers that could not be retrieved are listed in `missing`.
    """
    if not tickers or len(tickers) > MAX_TICKERS:
        raise ValueError(f"Provide between 1 and {MAX_TICKERS} tickers")
    symbols = list(dict.fromkeys(_ticker(t) for t in tickers))
    quotes, rate_limited = get_quotes_with_status(symbols)
    found = {q["ticker"] for q in quotes}
    return {"quotes": quotes, "missing": [s for s in symbols if s not in found], "rate_limited": rate_limited}


@mcp.tool()
def get_market_overview(period: Period = "1mo") -> dict:
    """Major index and sector ETF quotes plus index levels and normalized (start=100) performance for a period."""
    data = _market_overview(period)
    return {
        "indices": data["indices"],
        "sectors": data["sectors"],
        "normalized_performance": _frame_records(data["history"]),
        "index_levels": _frame_records(data["index_levels"]),
        "as_of": data["as_of"].isoformat(),
        "missing_quotes": data["missing_quotes"],
        "period": period,
    }


@mcp.tool()
def get_financial_news(terms: list[str] | None = None, limit: int | None = None) -> dict:
    """Recent financial headlines from the RSS feeds in config.yaml, optionally filtered by keywords.

    If no headline matches `terms`, general headlines are returned (existing app behavior).
    """
    data = load_config()["data"]
    limit = data.get("max_news_items", 8) if limit is None else limit
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_NEWS:
        raise ValueError(f"limit must be an integer between 1 and {MAX_NEWS}")
    cleaned = [t.strip() for t in (terms or []) if isinstance(t, str) and t.strip()]
    items, feed_failures = fetch_news_with_status(data["news_feeds"], cleaned or None, limit)
    return {"items": items, "some_feeds_failed": feed_failures}


@mcp.tool()
def analyze_portfolio(holdings: list[dict], include_sector: bool = True) -> dict:
    """Value, weights, gain/loss, concentration (HHI) and sector mix for holdings at current quotes.

    Each holding: {"ticker": str, "shares": number > 0, "cost_basis": optional per-share number >= 0}.
    Nothing is stored; tickers that cannot be priced are listed in `skipped`.
    """
    if not holdings or len(holdings) > MAX_HOLDINGS:
        raise ValueError(f"Provide between 1 and {MAX_HOLDINGS} holdings")
    clean = []
    for h in holdings:
        if not isinstance(h, dict):
            raise ValueError("Each holding must be an object with ticker and shares")
        item = {"ticker": _ticker(h.get("ticker")),
                "shares": _finite(h.get("shares"), "shares", minimum=0)}
        if item["shares"] <= 0:
            raise ValueError("shares must be greater than 0")
        if h.get("cost_basis") is not None:
            item["cost_basis"] = _finite(h["cost_basis"], "cost_basis", minimum=0)
        clean.append(item)
    return _analyze_portfolio(clean, include_sector=include_sector)


@mcp.tool()
def project_future_value(present: float, monthly: float, annual_rate: float, years: float) -> dict:
    """Future value of savings with monthly contributions and monthly compounding.

    annual_rate is a decimal (0.07 = 7%).
    """
    args = (_finite(present, "present", minimum=0), _finite(monthly, "monthly", minimum=0),
            _finite(annual_rate, "annual_rate", minimum=-0.99, maximum=1),
            _finite(years, "years", minimum=0, maximum=MAX_YEARS))
    return {"future_value": calculators.future_value(*args)}


@mcp.tool()
def required_monthly_contribution(target: float, present: float, annual_rate: float, years: float) -> dict:
    """Monthly contribution needed to reach a target; annual_rate is a decimal (0.07 = 7%)."""
    args = (_finite(target, "target", minimum=0), _finite(present, "present", minimum=0),
            _finite(annual_rate, "annual_rate", minimum=-0.99, maximum=1),
            _finite(years, "years", minimum=0, maximum=MAX_YEARS))
    return {"required_monthly_contribution": calculators.required_monthly_contribution(*args)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
