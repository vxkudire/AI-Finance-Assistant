"""Portfolio maths: values, weights, gain/loss, concentration (HHI) and sector mix."""
import yfinance as yf
import streamlit as st

from src.data.market_data import get_quote
from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning
from src.utils.api_errors import ServiceUnavailable, call_with_retry, is_rate_limit
from src.utils.logger import get_logger

log = get_logger("portfolio")


def _num(v):
    try:
        f = float(v)
        return f if f == f else None   # drops NaN
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=3600, max_entries=500)
def _sector(ticker: str, cache_version: str | int = 0) -> str:
    try:
        with ignore_yfinance_dataframe_inplace_warning():
            info = call_with_retry(lambda: yf.Ticker(ticker).info, "Yahoo Finance")
        sector = info.get("sector") or info.get("quoteType")
        if not sector:
            raise ServiceUnavailable("Yahoo Finance")
        return sector
    except Exception as exc:
        raise ServiceUnavailable("Yahoo Finance", rate_limited=is_rate_limit(exc)) from exc


def analyze_portfolio(
    holdings: list[dict], include_sector: bool = True, cache_version: str | int = 0
) -> dict:
    rows, skipped = [], []

    def skip_remaining(position: int) -> None:
        for item in holdings[position + 1:]:
            ticker = str(item.get("ticker", "")).upper().strip()
            shares_left = _num(item.get("shares"))
            if ticker and shares_left and shares_left > 0:
                skipped.append(ticker)

    for position, h in enumerate(holdings):
        t, shares = str(h.get("ticker", "")).upper().strip(), _num(h.get("shares"))
        if not t or not shares or shares <= 0:
            continue
        try:
            q = get_quote(t, cache_version)
        except ServiceUnavailable as exc:
            log.warning("Portfolio quote unavailable for %s (%s)", t, "rate limited" if exc.rate_limited else "provider failure")
            skipped.append(t)
            if exc.rate_limited:
                skip_remaining(position)
                break
            continue
        if not q:
            skipped.append(t)
            continue
        cb = _num(h.get("cost_basis"))
        mv = shares * q["price"]
        rate_limited = False
        try:
            sector = _sector(t, cache_version) if include_sector else "n/a"
        except ServiceUnavailable as exc:
            log.warning("Sector data unavailable for %s (%s)", t, "rate limited" if exc.rate_limited else "provider failure")
            sector = "Unknown"
            rate_limited = exc.rate_limited
        rows.append({"ticker": t, "shares": shares, "price": q["price"], "value": mv, "cost_basis": cb,
                     "gain_pct": (q["price"] / cb - 1) * 100 if cb else None,
                     "sector": sector})
        if rate_limited:
            skip_remaining(position)
            break
    total = sum(r["value"] for r in rows)
    for r in rows:
        r["weight"] = r["value"] / total if total else 0.0
    hhi = sum(r["weight"] ** 2 for r in rows)
    sectors: dict[str, float] = {}
    for r in rows:
        sectors[r["sector"]] = sectors.get(r["sector"], 0.0) + r["weight"]
    return {"rows": rows, "total_value": total, "top_weight": max((r["weight"] for r in rows), default=0.0),
            "hhi": hhi, "effective_holdings": (1 / hhi) if hhi else 0.0, "sectors": sectors, "skipped": skipped}


def format_portfolio_report(a: dict) -> str:
    if not a["rows"]:
        return "No holdings could be priced. Ask the user to check the tickers or retry later if market data is unavailable."
    lines = [f"{'Partial value (priced holdings only)' if a['skipped'] else 'Total value'}: ${a['total_value']:,.2f}",
             f"Largest position: {a['top_weight']:.1%} | Herfindahl index (HHI): {a['hhi']:.3f} | "
             f"effective number of equal-weight holdings: {a['effective_holdings']:.1f}",
             "Holdings:"]
    for r in sorted(a["rows"], key=lambda r: -r["weight"]):
        gl = f", gain/loss {r['gain_pct']:+.1f}%" if r["gain_pct"] is not None else ""
        lines.append(f"- {r['ticker']}: {r['shares']:g} sh @ {r['price']:.2f} = ${r['value']:,.0f} "
                     f"({r['weight']:.1%}, {r['sector']}{gl})")
    lines.append("Sector/type mix: " + ", ".join(f"{k} {v:.0%}" for k, v in
                                                  sorted(a["sectors"].items(), key=lambda kv: -kv[1])))
    if a["skipped"]:
        lines.append("Could not price: " + ", ".join(a["skipped"]))
    return "\n".join(lines)
