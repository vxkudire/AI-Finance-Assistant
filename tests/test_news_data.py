from types import SimpleNamespace

from src.data import news_data


def test_news_caches_feed_response_but_applies_terms_per_request(monkeypatch):
    calls = []

    def parse(url):
        calls.append(url)
        return SimpleNamespace(
            feed={"title": "Finance Daily"},
            entries=[
                {"title": "Rates hold steady", "summary": "Central bank update"},
                {"title": "Earnings rise", "summary": "Company results"},
            ],
        )

    news_data._fetch_feed.clear()
    monkeypatch.setattr(news_data.feedparser, "parse", parse)

    try:
        rates = news_data.fetch_news(["https://example.test/rss"], ["rates"])
        earnings = news_data.fetch_news(["https://example.test/rss"], ["earnings"])

        assert [item["title"] for item in rates] == ["Rates hold steady"]
        assert [item["title"] for item in earnings] == ["Earnings rise"]
        assert calls == ["https://example.test/rss"]
    finally:
        news_data._fetch_feed.clear()
