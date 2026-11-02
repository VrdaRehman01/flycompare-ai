"""Email captured during tests (shared module, so pytest's conftest and test imports see one list)."""

import re

OUTBOX: list[dict] = []


def last_code(email: str) -> str:
    """The six-digit code in the newest captured email to ``email``."""
    message = next(m for m in reversed(OUTBOX) if m["to"] == email)
    return re.search(r"\b(\d{6})\b", message["text"]).group(1)
