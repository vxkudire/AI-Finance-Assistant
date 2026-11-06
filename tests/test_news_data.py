from io import BytesIO

from src.data import news_data


def test_news_caches_feed_response_but_applies_terms_per_request(monkeypatch):
    calls = []

    def open_feed(request, timeout):
        calls.append(request.full_url)
        assert timeout == 8
        return BytesIO(b"""<?xml version="1.0"?>
            <rss version="2.0"><channel><title>Finance Daily</title>
            <item><title>Rates hold steady</title><description>Central bank update</description></item>
            <item><title>Earnings rise</title><description>Company results</description></item>
            </channel></rss>""")

    news_data._fetch_feed.clear()
    monkeypatch.setattr(news_data, "urlopen", open_feed)

    try:
        rates = news_data.fetch_news(["https://example.test/rss"], ["rates"])
        earnings = news_data.fetch_news(["https://example.test/rss"], ["earnings"])

        assert [item["title"] for item in rates] == ["Rates hold steady"]
        assert [item["title"] for item in earnings] == ["Earnings rise"]
        assert calls == ["https://example.test/rss"]
    finally:
        news_data._fetch_feed.clear()
