"""Financial news from RSS feeds listed in config.yaml (no API key required)."""
import re

import feedparser


def _clean(html: str, n: int = 300) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()[:n]


def fetch_news(feeds: list[str], terms: list[str] | None = None, limit: int = 8) -> list[dict]:
    items = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        source = parsed.feed.get("title", url)
        for e in parsed.entries[:25]:
            items.append({"source": source, "title": e.get("title", ""), "summary": _clean(e.get("summary", "")),
                          "published": e.get("published", ""), "link": e.get("link", "")})
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
