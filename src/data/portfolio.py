"""Portfolio maths: values, weights, gain/loss, concentration (HHI) and sector mix."""
import yfinance as yf

from src.data.market_data import get_quote
from src.data.yfinance_compat import ignore_yfinance_dataframe_inplace_warning


def _num(v):
    try:
        f = float(v)
        return f if f == f else None   # drops NaN
    except (TypeError, ValueError):
        return None


def _sector(ticker: str) -> str:
    try:
        with ignore_yfinance_dataframe_inplace_warning():
            info = yf.Ticker(ticker).info
        return info.get("sector") or info.get("quoteType") or "Unknown"
    except Exception:
        return "Unknown"


def analyze_portfolio(holdings: list[dict], include_sector: bool = True) -> dict:
    rows, skipped = [], []
    for h in holdings:
        t, shares = str(h.get("ticker", "")).upper().strip(), _num(h.get("shares"))
        if not t or not shares or shares <= 0:
            continue
        q = get_quote(t)
        if not q:
            skipped.append(t)
            continue
        cb = _num(h.get("cost_basis"))
        mv = shares * q["price"]
        rows.append({"ticker": t, "shares": shares, "price": q["price"], "value": mv, "cost_basis": cb,
                     "gain_pct": (q["price"] / cb - 1) * 100 if cb else None,
                     "sector": _sector(t) if include_sector else "n/a"})
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
        return "No valid holdings could be priced. Ask the user to check the tickers."
    lines = [f"Total value: ${a['total_value']:,.2f}",
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
