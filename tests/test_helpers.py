from src.utils.helpers import extract_tickers


def test_extract_tickers():
    assert extract_tickers("How is AAPL doing vs MSFT?") == ["AAPL", "MSFT"]
    assert extract_tickers("what about $nvda?") == ["NVDA"]
    assert extract_tickers("Explain a Roth IRA") == []
