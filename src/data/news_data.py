"""Financial news from RSS feeds listed in config.yaml (no API key required)."""
import re

import feedparser
import streamlit as st


def _clean(html: str, n: int = 300) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()[:n]


@st.cache_data(ttl=300, max_entries=32)
def _fetch_feed(url: str) -> list[dict]:
    try:
        parsed = feedparser.parse(url)
    except Exception:
        return []
    source = parsed.feed.get("title", url)
    return [
        {"source": source, "title": e.get("title", ""), "summary": _clean(e.get("summary", "")),
         "published": e.get("published", ""), "link": e.get("link", "")}
        for e in parsed.entries[:25]
    ]


def fetch_news(feeds: list[str], terms: list[str] | None = None, limit: int = 8) -> list[dict]:
    items = [item for url in feeds for item in _fetch_feed(url)]
    if terms:
        t = [x.lower() for x in terms]
        matched = [i for i in items if any(x in f"{i['title']} {i['summary']}".lower() for x in t)]
        items = matched or items      # fall back to general headlines if nothing matches
    return items[:limit]


def format_news(items: list[dict]) -> str:
    if not items:
        return "No news items could be retrieved. Tell the user."
    return "\n".join(f"{i}. [{n['source']}] {n['title']} ({n['published']})\n   {n['summary']}\n   {n['link']}"
                     for i, n in enumerate(items, 1))
