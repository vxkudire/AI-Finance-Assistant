import re

DISCLAIMER = (
    "_General educational information only - not personalised financial, investment, or tax advice. "
    "Consider speaking with a licensed professional before acting._"
)

# Loose match: tolerates italics markers, a preceding '---' rule, whitespace/punctuation drift and a missing
# final period, so copies echoed or reworded by a model are removed too.
_DISCLAIMER_RE = re.compile(
    r"(?:\n*-{3,}[ \t]*)?\n*[_*]*\s*General\s+educational\s+information\s+only\b.{0,300}?"
    r"licensed professional(?:\s+before\s+acting)?[.\s]*[_*]*",
    re.IGNORECASE | re.DOTALL,
)


def strip_disclaimer(text: str) -> str:
    """Remove every copy of the disclaimer so it can be appended exactly once."""
    return _DISCLAIMER_RE.sub("", text).rstrip()


def add_disclaimer(text: str) -> str:
    return f"{strip_disclaimer(text)}\n\n---\n{DISCLAIMER}"
