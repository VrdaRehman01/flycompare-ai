"""Small in-process sliding-window rate limiter.

Suitable for a single API process. A multi-process deployment should move this
to a shared store such as Redis so limits apply across processes.
"""

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                # Visible in the logs for spotting abuse; the key is "<kind>:<client>", never personal data.
                logger.warning("Rate limit reached for %s", key)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_auth(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_enabled:
        limiter.check(f"auth:{_client_key(request)}", settings.rate_limit_auth_per_minute)


def limit_search(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_enabled:
        limiter.check(f"search:{_client_key(request)}", settings.rate_limit_search_per_minute)
        # Shared ceiling across all visitors: protects provider quotas even if addresses rotate.
        limiter.check("search:all", settings.rate_limit_search_global_per_minute)
