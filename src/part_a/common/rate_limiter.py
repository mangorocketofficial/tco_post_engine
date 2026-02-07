"""Token-bucket rate limiter for polite scraping."""

from __future__ import annotations

import time
import threading


class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Args:
        requests_per_minute: Maximum requests allowed per minute.
    """

    def __init__(self, requests_per_minute: int = 20) -> None:
        self._interval = 60.0 / max(requests_per_minute, 1)
        self._last_request_time: float = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until the next request is allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_request_time = time.monotonic()
