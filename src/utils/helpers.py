import re

from langchain_core.messages import BaseMessage

_STOP = {
    "THE", "AND", "FOR", "ARE", "YOU", "NOT", "BUT", "CAN", "HOW", "WHY", "WHAT", "WHO", "NOW", "NEW", "ALL",
    "ETF", "IRA", "USD", "CEO", "IPO", "GDP", "CPI", "FED", "SEC", "IRS", "TAX", "BUY", "SELL", "ROTH", "EPS",
    "NEWS", "TODAY", "STOCK", "STOCKS", "MARKET", "HSA", "FDIC", "APR", "APY", "ROI", "AI", "US", "UK", "VS",
}
_GENERIC = {
    "latest", "news", "what", "happening", "today", "summarize", "summary", "about", "market", "markets",
    "stock", "stocks", "tell", "please", "explain", "recent", "headlines", "going", "would", "could", "should",
}


def message_text(msg: BaseMessage) -> str:
    c = msg.content
    if isinstance(c, str):
        return c
    return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)


def last_user_text(messages) -> str:
    for m in reversed(messages):
        if getattr(m, "type", "") == "human":
            return message_text(m)
    return ""


def extract_tickers(text: str, limit: int = 5) -> list[str]:
    """Heuristic: `$aapl` or bare ALL-CAPS tokens (2-5 letters) that are not common words."""
    found: list[str] = []
    for m in re.finditer(r"\$([A-Za-z]{1,5})\b|\b([A-Z]{2,5})\b", text):
        sym = (m.group(1) or m.group(2)).upper()
        if m.group(2) and sym in _STOP:
            continue
        if sym not in found:
            found.append(sym)
    return found[:limit]


def topic_terms(text: str) -> list[str]:
    """Tickers + meaningful words (>4 letters) used to filter news."""
    words = [w.lower() for w in re.findall(r"[A-Za-z]{5,}", text) if w.lower() not in _GENERIC]
    return extract_tickers(text) + words
