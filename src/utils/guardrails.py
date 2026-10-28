DISCLAIMER = (
    "_General educational information only - not personalised financial, investment, or tax advice. "
    "Consider speaking with a licensed professional before acting._"
)


def add_disclaimer(text: str) -> str:
    return f"{text.rstrip()}\n\n---\n{DISCLAIMER}"
