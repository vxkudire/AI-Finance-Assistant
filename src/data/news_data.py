"""Financial news from RSS feeds listed in config.yaml (no API key required)."""
import re
from urllib.request import Request, urlopen

import feedparser
import streamlit as st

from src.utils.api_errors import call_with_retry, is_rate_limit
from src.utils.logger import get_logger

log = get_logger("news_data")


def _clean(html: str, n: int = 300) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()[:n]


@st.cache_data(ttl=300, max_entries=32)
def _fetch_feed(url: str) -> list[dict]:
    def download():
        request = Request(url, headers={"User-Agent": "AI-Finance-Assistant/1.0"})
        with urlopen(request, timeout=8) as response:
            return response.read()

    parsed = feedparser.parse(call_with_retry(download, "News feed"))
    if parsed.get("bozo") and not parsed.entries:
        raise ValueError("News feed could not be parsed")
    source = parsed.feed.get("title", url)
    return [
        {"source": source, "title": e.get("title", ""), "summary": _clean(e.get("summary", "")),
         "published": e.get("published", ""), "link": e.get("link", "")}
        for e in parsed.entries[:25]
    ]


def fetch_news_with_status(
    feeds: list[str], terms: list[str] | None = None, limit: int = 8
) -> tuple[list[dict], bool]:
    items = []
    failed = False
    for url in feeds:
        try:
            items.extend(_fetch_feed(url))
        except Exception as exc:
            failed = True
            log.warning("News feed unavailable (%s)", type(exc).__name__)
            if is_rate_limit(exc):
                break
    if terms:
        t = [x.lower() for x in terms]
        matched = [i for i in items if any(x in f"{i['title']} {i['summary']}".lower() for x in t)]
        items = matched or items      # fall back to general headlines if nothing matches
    return items[:limit], failed


def fetch_news(feeds: list[str], terms: list[str] | None = None, limit: int = 8) -> list[dict]:
    return fetch_news_with_status(feeds, terms, limit)[0]


def format_news(items: list[dict]) -> str:
    if not items:
        return "No news items could be retrieved. Tell the user."
    return "\n".join(f"{i}. [{n['source']}] {n['title']} ({n['published']})\n   {n['summary']}\n   {n['link']}"
                     for i, n in enumerate(items, 1))
