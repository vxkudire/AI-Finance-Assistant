"""Bounded retries and safe messages for external service failures."""
import random
import math
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Callable, TypeVar
from urllib.error import URLError

from src.utils.logger import get_logger

T = TypeVar("T")
log = get_logger("api")
MAX_ATTEMPTS = 3
MAX_RETRY_DELAY = 2.0


class ServiceUnavailable(Exception):
    def __init__(self, service: str, *, rate_limited: bool = False):
        super().__init__(f"{service} is temporarily unavailable")
        self.service = service
        self.rate_limited = rate_limited


def http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return (getattr(exc, "status_code", None) or getattr(exc, "status", None)
            or getattr(exc, "code", None) or getattr(response, "status_code", None))


def is_rate_limit(exc: Exception) -> bool:
    return (isinstance(exc, ServiceUnavailable) and exc.rate_limited) or http_status(exc) == 429 or (
        exc.__class__.__name__ in {"YFRateLimitError", "RateLimitError", "TooManyRequests"}
    )


def is_transient(exc: Exception) -> bool:
    status = http_status(exc)
    return is_rate_limit(exc) or status in {408, 500, 502, 503, 504} or isinstance(
        exc, (TimeoutError, ConnectionError)
    ) or (isinstance(exc, URLError) and status is None) or exc.__class__.__name__ in {
        "Timeout", "ConnectTimeout", "ReadTimeout", "ConnectionError", "APITimeoutError", "APIConnectionError"
    }


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None) or {}
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if math.isfinite(seconds) else None
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def call_with_retry(operation: Callable[[], T], service: str) -> T:
    """Retry transient failures only; never retry before a long Retry-After."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            return operation()
        except Exception as exc:
            if not is_transient(exc) or attempt == MAX_ATTEMPTS - 1:
                raise
            delay = _retry_after(exc)
            if delay is not None and delay > MAX_RETRY_DELAY:
                raise
            delay = delay if delay is not None else random.uniform(0.25, 0.5) * 2 ** attempt
            log.warning("%s request failed (%s); retrying", service, type(exc).__name__)
            time.sleep(delay)
    raise AssertionError("unreachable")


def user_error_message(exc: Exception) -> str:
    if is_rate_limit(exc):
        return "A service is receiving too many requests. Please wait a moment and try again."
    if http_status(exc) in {401, 403}:
        return "A service could not be accessed. Please contact the administrator."
    if isinstance(exc, ServiceUnavailable) or is_transient(exc) or http_status(exc):
        return "A service is temporarily unavailable. Please try again later."
    return "The request could not be completed. Please try again later."
