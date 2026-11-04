from src.utils.guardrails import DISCLAIMER, add_disclaimer, strip_disclaimer
from src.utils.helpers import extract_tickers


def test_disclaimer_appears_once_even_if_echoed():
    echoed = f"Answer.\n\n---\n{DISCLAIMER}\n\n{DISCLAIMER.strip('_')}"
    out = add_disclaimer(echoed)
    assert out.count("General educational information only") == 1
    assert out.endswith(DISCLAIMER)
    assert add_disclaimer(out) == out
    assert strip_disclaimer(out) == "Answer."


def test_disclaimer_dedupes_reworded_copies():
    variant = (
        "Answer.\n\n---\n*General educational information only - not personalised financial, investment, or tax "
        "advice. Consider speaking with a licensed professional before acting*\n\n"
        "General  educational information only - not personalised advice. Consider speaking with a licensed "
        "professional before acting"
    )
    out = add_disclaimer(variant)
    assert out.lower().count("general educational information only") == 1
    assert out == add_disclaimer("Answer.")


def test_extract_tickers():
    assert extract_tickers("How is AAPL doing vs MSFT?") == ["AAPL", "MSFT"]
    assert extract_tickers("what about $nvda?") == ["NVDA"]
    assert extract_tickers("Explain a Roth IRA") == []
